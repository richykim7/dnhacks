"""Local cross-process repair batching with scoped records and durable successful responses."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter, deque
from pathlib import Path


MAX_MESSAGE = 8 * 1024 * 1024


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _parse(response):
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


class RepairQueue:
    def __init__(self, path, call_model, batch_size=10, max_concurrency=10, cache_dir=None):
        if type(batch_size) is not int or batch_size < 1 or type(max_concurrency) is not int or max_concurrency < 1:
            raise ValueError("batch_size and max_concurrency must be positive integers")
        self.path = Path(path)
        self.call_model = call_model
        self.batch_size, self.max_concurrency = batch_size, max_concurrency
        self.cache = Path(cache_dir) if cache_dir is not None else self.path.parent / "repair-response-cache"
        self.pending = deque()
        self.active = set()
        self.waiting = Counter()
        self.running = set()
        self.clients = set()
        self.server = None
        self.draining = False
        self.closing = False
        self.halted = None
        self.sequence = 0
        self.stats = Counter()

    async def start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.server = await asyncio.start_unix_server(self._connection, str(self.path), limit=MAX_MESSAGE)
        self.path.chmod(0o600)
        return self

    async def set_active(self, owner: str, active: bool):
        if active:
            self.active.add(owner)
        else:
            self.active.discard(owner)
        self._pump()

    async def drain(self):
        self.draining = True
        self._pump()
        while self.running or self.pending:
            if self.running:
                await asyncio.gather(*tuple(self.running), return_exceptions=True)
            self._pump()

    async def close(self):
        self.closing = True
        if self.server is not None:
            self.server.close()
        self._fail_pending("Repair queue closed")
        for task in tuple(self.running):
            task.cancel()
        if self.running:
            await asyncio.gather(*tuple(self.running), return_exceptions=True)
        for task in tuple(self.clients):
            task.cancel()
        if self.clients:
            await asyncio.gather(*tuple(self.clients), return_exceptions=True)
        if self.server is not None:
            await self.server.wait_closed()
            self.path.unlink(missing_ok=True)
            self.server = None

    async def _connection(self, reader, writer):
        task = asyncio.current_task()
        self.clients.add(task)
        try:
            line = await reader.readline()
            request = json.loads(line)
            results = await self._submit(request["owner"], request["records"], request["instructions"])
            response = {"results": results}
        except (Exception, asyncio.CancelledError) as exc:
            response = {"error": f"{type(exc).__name__}: {str(exc) or 'Repair queue closed'}"}
        try:
            writer.write((_json(response) + "\n").encode())
            await writer.drain()
        except (ConnectionError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            finally:
                self.clients.discard(task)

    async def _submit(self, owner, records, instructions):
        if self.closing or self.halted:
            raise RuntimeError(self.halted or "Repair queue closed")
        if not isinstance(owner, str) or not owner or not isinstance(instructions, str) or not isinstance(records, list):
            raise ValueError("owner, records and instructions have invalid types")
        seen = set()
        for record in records:
            if not isinstance(record, dict) or record.get("source_owner") != owner:
                raise ValueError("every record must have its submitting source_owner")
            local_id = record.get("id")
            if type(local_id) not in (int, str) or (type(local_id), local_id) in seen:
                raise ValueError("record ids must be unique strings or integers")
            seen.add((type(local_id), local_id))
        futures = []
        self.stats["records_submitted"] += len(records)
        self.waiting[owner] += 1
        try:
            for record in records:
                key = _hash({"record": {k: v for k, v in record.items() if k != "id"}, "instructions": instructions})
                future = asyncio.get_running_loop().create_future()
                cache_path = self.cache / f"{key}.json"
                if cache_path.exists():
                    cached = json.loads(cache_path.read_text())
                    if cached.get("status") not in {"corrected", "rejected", "unresolved"}:
                        raise ValueError("Invalid repair response cache")
                    future.set_result({**cached, "id": record["id"]})
                    self.stats["cache_hits"] += 1
                else:
                    self.sequence += 1
                    self.pending.append({"record": record, "instructions": instructions, "key": key,
                                         "id": f"q{self.sequence}", "future": future})
                futures.append(future)
            self._pump()
            # Drain every record even if one batch failed; one failed future must not strand others.
            outcomes = await asyncio.gather(*futures, return_exceptions=True)
            error = next((r for r in outcomes if isinstance(r, BaseException)), None)
            if error is not None:
                raise RuntimeError(str(error))
            return outcomes
        finally:
            self.waiting[owner] -= 1
            if not self.waiting[owner]:
                del self.waiting[owner]
            self._pump()

    def _pump(self):
        if self.closing or self.halted:
            return
        while self.pending and len(self.running) < self.max_concurrency:
            full = len(self.pending) >= self.batch_size
            blocked = not self.running and self.active.issubset(self.waiting)
            if not full and not (self.draining or blocked):
                return
            batch = [self.pending.popleft() for _ in range(min(self.batch_size, len(self.pending)))]
            task = asyncio.create_task(self._batch(batch))
            self.running.add(task)
            task.add_done_callback(self._finished)

    def _finished(self, task):
        self.running.discard(task)
        self._pump()

    def _fail_pending(self, message):
        while self.pending:
            item = self.pending.popleft()
            if not item["future"].done():
                item["future"].set_exception(RuntimeError(message))

    def _halt(self, message):
        self.halted = message
        self._fail_pending(message)

    async def _batch(self, batch):
        try:
            schemas = {_hash(item["instructions"]): item["instructions"] for item in batch}
            records = [{**item["record"], "id": item["id"], "schema_id": _hash(item["instructions"])}
                       for item in batch]
            try:
                self.stats["model_calls"] += 1
                response = await self.call_model(_json({"schemas": schemas, "records": records}))
            except Exception as exc:
                self._halt("Repair model unavailable: " + str(exc))
                raise
            parsed = _parse(response)
            rows = parsed.get("results") if isinstance(parsed, dict) else None
            expected = {item["id"] for item in batch}
            if not isinstance(rows, list) or len(rows) != len(expected):
                raise ValueError("Repair response must contain exactly one result per record")
            found = {}
            for row in rows:
                if not isinstance(row, dict) or row.get("id") not in expected or row["id"] in found:
                    raise ValueError("Repair response has missing, duplicate or unknown ids")
                if row.get("status") not in {"corrected", "rejected", "unresolved"}:
                    raise ValueError("Repair response has invalid status")
                if row.get("status") == "unresolved" and any(term in str(row.get("reason", "")).lower()
                        for term in ("service unavailable", "session limit", "rate limit", "quota", "authentication")):
                    self._halt("Repair model unavailable: " + str(row.get("reason")))
                    raise RuntimeError("Repair model unavailable: " + str(row.get("reason")))
                if row["status"] == "corrected" and not isinstance(row.get("raw"), dict):
                    raise ValueError("Corrected repair response requires raw record")
                found[row["id"]] = row
            for item in batch:
                row = found[item["id"]]
                cached = {k: v for k, v in row.items() if k != "id"}
                path = self.cache / f"{item['key']}.json"
                temporary = path.with_suffix(f".{item['id']}.tmp")
                temporary.write_text(_json(cached))
                temporary.replace(path)
                if not item["future"].done():
                    item["future"].set_result({**cached, "id": item["record"]["id"]})
                    self.stats["records_completed"] += 1
        except (Exception, asyncio.CancelledError) as exc:
            self.stats["failed_batches"] += 1
            for item in batch:
                if not item["future"].done():
                    item["future"].set_exception(RuntimeError(str(exc) or "Repair queue closed"))


async def submit(socket_path, owner, records, instructions):
    request = (_json({"owner": owner, "records": records, "instructions": instructions}) + "\n").encode()
    if len(request) > MAX_MESSAGE:
        raise ValueError("Repair request exceeds 8 MB")
    reader, writer = await asyncio.open_unix_connection(str(socket_path), limit=MAX_MESSAGE)
    try:
        writer.write(request)
        await writer.drain()
        line = await reader.readline()
        if not line:
            raise RuntimeError("Repair queue connection closed before response")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response["results"]
    finally:
        writer.close()
        await writer.wait_closed()

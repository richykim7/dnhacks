import asyncio
import json

import pytest

from dnhacksbio.litmap.repair_queue import RepairQueue, submit


def records(owner, count):
    return [{"id": i, "source_owner": owner, "raw": {"quote": f"{owner} finding {i}"}}
            for i in range(count)]


def answer(prompt):
    data = json.loads(prompt)
    return json.dumps({"results": [{"id": r["id"], "status": "corrected", "raw": r["raw"]}
                                    for r in data["records"]]})


@pytest.mark.parametrize("first_size", [5, 9])
def test_exact_tens_merge_owners_and_preserve_local_ids(tmp_path, first_size):
    async def check():
        calls = []

        async def model(prompt):
            calls.append(json.loads(prompt))
            return answer(prompt)

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        try:
            for owner in ("paper-a", "paper-b"):
                await queue.set_active(owner, True)
            first = asyncio.create_task(submit(queue.path, "paper-a", records("paper-a", first_size), "schema"))
            await asyncio.sleep(0.02)
            assert not calls, "partial batch launched while another owner could produce"
            second = asyncio.create_task(submit(queue.path, "paper-b", records("paper-b", 10 - first_size), "schema"))
            a, b = await asyncio.wait_for(asyncio.gather(first, second), 3)
            assert len(calls) == 1 and len(calls[0]["records"]) == 10
            assert len(calls[0]["schemas"]) == 1
            assert {r["source_owner"] for r in calls[0]["records"]} == {"paper-a", "paper-b"}
            assert [r["id"] for r in a] == list(range(first_size))
            assert [r["id"] for r in b] == list(range(10 - first_size))
            assert all(r["raw"]["quote"].startswith("paper-a") for r in a)
            assert all(r["raw"]["quote"].startswith("paper-b") for r in b)
        finally:
            await queue.close()
    asyncio.run(check())


def test_large_request_splits_and_flushes_final_tail_without_deadlock(tmp_path):
    async def check():
        sizes = []

        async def model(prompt):
            sizes.append(len(json.loads(prompt)["records"]))
            await asyncio.sleep(0)
            return answer(prompt)

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        try:
            await queue.set_active("paper", True)
            result = await asyncio.wait_for(submit(queue.path, "paper", records("paper", 25), "schema"), 3)
            assert sizes == [10, 10, 5]
            assert [r["id"] for r in result] == list(range(25))
        finally:
            await queue.close()
    asyncio.run(check())


def test_global_model_concurrency_cap(tmp_path):
    async def check():
        active = peak = 0
        sizes = []
        barrier = asyncio.Event()

        async def model(prompt):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            sizes.append(len(json.loads(prompt)["records"]))
            if active == 10:
                barrier.set()
            await barrier.wait()
            await asyncio.sleep(0)
            active -= 1
            return answer(prompt)

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        try:
            await queue.set_active("paper", True)
            result = await asyncio.wait_for(submit(queue.path, "paper", records("paper", 125), "schema"), 3)
            assert peak == 10 and active == 0
            assert sizes == [10] * 12 + [5]
            assert len(result) == 125
        finally:
            await queue.close()
    asyncio.run(check())


def test_cache_restart_reuses_records_but_not_other_source_or_schema(tmp_path):
    async def check():
        calls = []

        async def model(prompt):
            calls.append(prompt)
            return answer(prompt)

        cache = tmp_path / "durable" / "cache"
        queue = await RepairQueue(tmp_path / "q.sock", model, cache_dir=cache).start()
        first = await submit(queue.path, "a", records("a", 2), "schema")
        await queue.close()
        queue = await RepairQueue(tmp_path / "q.sock", model, cache_dir=cache).start()
        try:
            assert await submit(queue.path, "a", records("a", 2), "schema") == first
            assert len(calls) == 1
            await submit(queue.path, "b", records("b", 2), "schema")
            await submit(queue.path, "a", records("a", 2), "changed schema")
            assert len(calls) == 3
        finally:
            await queue.close()
    asyncio.run(check())


@pytest.mark.parametrize("mode", ["exception", "duplicate", "missing", "invalid", "quota"])
def test_invalid_or_unavailable_batches_fail_explicitly_and_do_not_cache(tmp_path, mode):
    async def check():
        fail = True

        async def model(prompt):
            if not fail:
                return answer(prompt)
            data = json.loads(answer(prompt))
            if mode == "exception":
                raise RuntimeError("service unavailable")
            if mode == "duplicate":
                data["results"][1] = data["results"][0]
            elif mode == "missing":
                data["results"].pop()
            elif mode == "invalid":
                return "not JSON"
            else:
                data["results"][0].update(status="unresolved", reason="session limit")
            return json.dumps(data)

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        try:
            with pytest.raises(RuntimeError):
                await asyncio.wait_for(submit(queue.path, "paper", records("paper", 10), "schema"), 3)
            assert not list(queue.cache.glob("*.json"))
            fail = False
            if mode in {"exception", "quota"}:
                with pytest.raises(RuntimeError, match="unavailable"):
                    await submit(queue.path, "paper", records("paper", 10), "schema")
                await queue.close()
                queue = await RepairQueue(tmp_path / "q.sock", model).start()
            assert len(await asyncio.wait_for(submit(queue.path, "paper", records("paper", 10), "schema"), 3)) == 10
        finally:
            await queue.close()
    asyncio.run(check())


@pytest.mark.parametrize("with_running", [False, True])
def test_close_cancels_inflight_and_fails_tail_without_launching_more(tmp_path, with_running):
    async def check():
        calls = 0
        cancelled = False
        started = asyncio.Event()

        async def model(prompt):
            nonlocal calls, cancelled
            calls += 1
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled = True
                raise

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        await queue.set_active("paper", True)
        await queue.set_active("producer", True)
        pending = asyncio.create_task(submit(queue.path, "paper", records("paper", 19 if with_running else 9), "schema"))
        if with_running:
            await asyncio.wait_for(started.wait(), 3)
        else:
            await asyncio.sleep(0.02)
        await asyncio.wait_for(queue.close(), 3)
        with pytest.raises(RuntimeError, match="closed"):
            await asyncio.wait_for(pending, 3)
        assert calls == (1 if with_running else 0)
        assert cancelled == with_running
        assert not queue.pending and not queue.running
    asyncio.run(check())


def test_service_exception_halts_unlaunched_batches_and_unblocks_client(tmp_path):
    async def check():
        calls = 0

        async def model(prompt):
            nonlocal calls
            calls += 1
            raise RuntimeError("quota exhausted")

        queue = await RepairQueue(tmp_path / "q.sock", model, max_concurrency=1).start()
        try:
            with pytest.raises(RuntimeError, match="quota"):
                await asyncio.wait_for(submit(queue.path, "paper", records("paper", 25), "schema"), 3)
            assert calls == 1 and not queue.pending
            assert not list(queue.cache.glob("*.json"))
        finally:
            await queue.close()
    asyncio.run(check())


def test_owner_mismatch_rejected_and_explicit_drain_releases_tail(tmp_path):
    async def check():
        async def model(prompt):
            return answer(prompt)

        queue = await RepairQueue(tmp_path / "q.sock", model).start()
        try:
            with pytest.raises(RuntimeError, match="source_owner"):
                await submit(queue.path, "a", records("b", 1), "schema")
            await queue.set_active("a", True)
            await queue.set_active("still-producing", True)
            pending = asyncio.create_task(submit(queue.path, "a", records("a", 1), "schema"))
            await asyncio.sleep(0.02)
            assert not pending.done()
            await asyncio.wait_for(queue.drain(), 3)
            assert len(await pending) == 1
        finally:
            await queue.close()
    asyncio.run(check())

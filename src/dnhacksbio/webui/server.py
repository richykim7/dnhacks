"""HTTP server for the engine web UI.

stdlib only. ThreadingHTTPServer so a long-lived SSE stream (the live run
tail) doesn't block other requests. Binds localhost by default — this exposes
run internals and writes review decisions, so it is not meant to face a network.

Routes
  GET  /                         -> the SPA shell
  GET  /assets/<file>            -> built React assets
  GET  /static/<file>            -> retained static assets
  GET  /api/runs                 -> flat run summaries (lineage-annotated)
  GET  /api/investigations       -> runs grouped into fork trees (root + branches)
  GET  /api/runs/<id>            -> full parsed run (steps, tallies, tests)
  GET  /api/runs/<id>/stream     -> SSE; new steps as they are appended
  GET  /api/kg?source=&limit=&status=&q=&polarity=&kind=&relation_class=&predicate=  -> KG nodes+edges
  GET  /api/kg?source=&claim=          -> one claim: evidence, context, papers, experiments, tests
  GET  /api/review               -> review queue (promotion candidates)
  GET  /api/architecture         -> the engine's shape + facts extracted from source
  GET  /api/events/<id>          -> the investigation's ordered event stream (the player)
  GET  /api/tree/<id>            -> the same investigation as a tree of experiments (the search tree)
  POST /api/review/promotion            -> record a promotion verdict
  POST /api/review/promotion/apply      -> apply recorded verdicts to the master graph

Projects — an analysis profile that scopes every view (see webui/projects.py)
  GET  /api/projects                          -> switcher summaries
  POST /api/projects                          -> create   {name, description, spec}
  GET  /api/projects/<id>                     -> the full record
  POST /api/projects/<id>                     -> update   {name, description, spec, status}
  POST /api/projects/<id>/delete              -> remove   {purge}
  GET  /api/projects/<id>/papers              -> local paper metadata
  GET  /api/projects/<id>/papers/<paper>      -> stored text and figure captions
  GET  /api/projects/<id>/papers/<paper>/figures/<index> -> local image
  GET  /api/projects/<id>/kg                  -> that project's graph in numbers
  GET  /api/projects/<id>/lane                -> the Workflow view's knowledge-graph lane, lit up
  POST /api/projects/<id>/build               -> start a corpus build   {mode, dry}
  POST /api/projects/<id>/run                 -> launch an explorer run   {goal, steps}
  GET  /api/projects/<id>/jobs                -> build history
  GET  /api/projects/<id>/jobs/<job>          -> one job + its progress events
  GET  /api/projects/<id>/jobs/<job>/stream   -> SSE; progress events as they are written
  GET  /api/projects/<id>/jobs/<job>/log      -> the child process's stderr tail
  POST /api/projects/<id>/jobs/<job>/cancel   -> stop a running build
  POST /api/projects/<id>/chat                -> one assistant turn   {message}
  POST /api/projects/<id>/chat/apply          -> accept a proposed spec patch   {patch}
  GET  /api/projects/<id>/attachments         -> uploaded documents
  POST /api/projects/<id>/attachments         -> upload (raw body; X-Filename header)
  POST /api/projects/<id>/attachments/<a>/delete
  POST /api/assistant/suggest                 -> one-shot spec from a description
"""

from __future__ import annotations

import asyncio
import json
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import architecture, assistant, attachments, data, jobs, projects, evidence, library, membership

STATIC = Path(__file__).resolve().parent / "static"
FRONTEND = Path(os.environ.get("DNHACKS_FRONTEND_DIST", Path(__file__).resolve().parents[3] / "frontend" / "dist"))

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".otf": "font/otf",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _json_safe(o):
    """Replace non-finite floats with null before serializing: `json.dumps` emits bare `NaN`, which
    browsers reject as invalid JSON, blanking the whole view. The UI renders null as missing."""
    if isinstance(o, float):
        return o if o == o and o not in (float("inf"), float("-inf")) else None
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


def _run_async(coro):
    """Run one coroutine to completion inside this request's thread.

    The assistant is async (it talks to the LLM seam) and this server is threads-and-blocking-IO.
    ThreadingHTTPServer gives every request its own thread, so a fresh event loop per call is both
    safe and simple — there is no shared loop for it to conflict with."""
    return asyncio.run(coro)


class Handler(BaseHTTPRequestHandler):
    server_version = "dnhacksbio-webui/1.0"
    protocol_version = "HTTP/1.1"

    # -- helpers -----------------------------------------------------------

    def _send_json(self, obj, status=200):
        body = json.dumps(_json_safe(obj)).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, msg):
        self._send_json({"error": msg}, status=status)

    def log_message(self, fmt, *args):  # quieter default logging
        pass

    # -- routing -----------------------------------------------------------

    def _project_arg(self, qs: dict) -> str | None:
        """The active project, if the client scoped the request to one.

        `project=all` is an explicit opt-out so a user can still see runs whose corpus cannot be
        identified. Absent means unscoped."""
        p = (qs.get("project") or [""])[0].strip()
        return None if p in ("", "all") else p

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/deployment/health":
                return self._send_json({"status": "ok", "release": os.environ.get("DNHACKS_RELEASE", "development"),
                                        "guarded": bool(os.environ.get("DNHACKS_DEPLOY_LOCK"))})
            if path == "/" or path == "/index.html":
                return self._serve_frontend("index.html")
            if path.startswith("/assets/"):
                return self._serve_frontend(unquote(path.lstrip("/")))
            if path.startswith("/static/"):
                return self._serve_static(path[len("/static/"):])
            if path.startswith("/api/runtime/"):
                from . import runtime
                return runtime.handle(self, unquote(path[len("/api/runtime/"):]), qs)
            if path == "/api/projects" or path.startswith("/api/projects/"):
                return self._projects_get(path, qs)
            if path == "/api/runs":
                include_all = (qs.get("all") or ["0"])[0] in ("1", "true")
                return self._send_json(data.list_runs(include_all=include_all,
                                                      project=self._project_arg(qs)))
            if path == "/api/investigations":
                include_all = (qs.get("all") or ["0"])[0] in ("1", "true")
                return self._send_json(data.investigations(include_all=include_all,
                                                           project=self._project_arg(qs)))
            if path.startswith("/api/runs/"):
                rest = path[len("/api/runs/"):]
                if rest.endswith("/stream"):
                    return self._stream_run(rest[: -len("/stream")], qs)
                return self._run_detail(rest)
            if path == "/api/kg":
                return self._kg(qs)
            if path == "/api/review/candidate":
                from .candidate_review import candidate
                return self._send_json(candidate(
                    (qs.get("run") or [""])[0], (qs.get("experiment") or [""])[0],
                    self._project_arg(qs)))
            if path == "/api/review":
                return self._send_json(data.review_queue(self._project_arg(qs)))
            if path == "/api/architecture":
                # The static shape + facts extracted from source. A rename raises ArchitectureDrift,
                # which surfaces as a 500 with the missing symbol named — the same signal the test gives.
                return self._send_json(architecture.build())
            if path.startswith("/api/events/"):
                return self._events(path[len("/api/events/"):])
            if path.startswith("/api/tree/"):
                return self._tree(path[len("/api/tree/"):])
            return self._error(404, "not found")
        except BrokenPipeError:
            return  # client went away mid-stream; nothing to do
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except ValueError as exc:      # bad project id / bad query argument
            return self._error(400, str(exc))
        except Exception as exc:  # never 500 silently — surface the reason
            traceback.print_exc()
            try:
                return self._error(500, f"{type(exc).__name__}: {exc}")
            except Exception:
                return

    def do_POST(self):
        from .deployment import Busy, lease
        try:
            with lease():
                return self._post()
        except Busy as exc:
            self.close_connection = True
            return self._error(503, str(exc))

    def _post(self):
        parsed = urlparse(self.path)
        # An attachment upload is bytes, not JSON. It is read here, before the JSON parse below
        # would choke on a PDF, and it is the only route that reads a raw body.
        if parsed.path.startswith("/api/projects/") and parsed.path.endswith(("/attachments", "/papers/upload")):
            return self._upload(parsed.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if '/inhibitor/' in parsed.path and not 0<=length<=65536:
                raise ValueError('Inhibitor request exceeds 64 KiB')
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            return self._error(400, "invalid JSON body")
        try:
            if parsed.path.startswith('/api/runtime/') and '/inhibitor/' in parsed.path:
                from dnhacksbio.inhibitor.service import Workbench
                from .runtime import journal
                parts=unquote(parsed.path[len('/api/runtime/'):]).split('/')
                if len(parts)!=3 or parts[1]!='inhibitor': raise ValueError('Invalid workbench path')
                qs=parse_qs(parsed.query)
                if 'through' in qs: raise ValueError('Playback is read-only')
                wb=Workbench(journal(),parts[0],parts[2],self._project_arg(qs))
                return self._send_json(wb.dispatch(payload,actor='user'))
            if parsed.path == "/api/projects" or parsed.path.startswith("/api/projects/"):
                return self._projects_post(parsed.path, payload)
            if parsed.path == "/api/assistant/suggest":
                res = _run_async(assistant.suggest(str(payload.get("description", "")),
                                                   str(payload.get("name", ""))))
                return self._send_json(res)
            if parsed.path == "/api/review/candidate":
                from .candidate_review import decide
                return self._send_json(decide(
                    str(payload.get("run", "")), str(payload.get("experiment", "")),
                    str(payload.get("decision", "")), str(payload.get("note", "")),
                    payload.get("project") or None))
            if parsed.path == "/api/review/promotion":
                res = data.record_promotion_decision(
                    test_id=payload.get("test_id"),
                    decision=str(payload.get("decision", "")),
                    note=str(payload.get("note", "")),
                    project=(payload.get("project") or None),
                )
                return self._send_json(res)
            if parsed.path == "/api/review/promotion/apply":
                return self._send_json(data.apply_promotions(payload.get("project") or None))
            return self._error(404, "not found")
        except assistant.AssistantUnavailable as exc:
            # 503, not 500: nothing is broken here, an upstream dependency is missing — and the
            # message tells the user the manual path is still open.
            return self._error(503, str(exc))
        except (ValueError, KeyError) as exc:
            return self._error(400, str(exc))
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except RuntimeError as exc:
            # ledger locked (active run): 409 Conflict
            return self._error(409, str(exc))
        except Exception as exc:
            traceback.print_exc()
            return self._error(500, f"{type(exc).__name__}: {exc}")

    # -- api: projects -----------------------------------------------------
    # One analysis = one project. These routes are the only way the browser creates state; every
    # other route in this file reads. Failures are surfaced with the reason a person can act on
    # (a bad spec field, a build already running) rather than a generic 500.

    def _project_or_404(self, pid: str) -> dict:
        try:
            return projects.load(pid)
        except KeyError:
            raise FileNotFoundError(f"no such project: {pid}")

    def _projects_get(self, path: str, qs: dict):
        rest = path[len("/api/projects"):].strip("/")
        if not rest:
            return self._send_json({"projects": projects.summaries()})
        parts = [unquote(p) for p in rest.split("/")]
        pid = parts[0]
        if len(parts) == 1:
            return self._send_json(self._project_or_404(pid))
        tail = parts[1]
        if tail == "papers":
            self._project_or_404(pid)
            if len(parts) == 2:
                return self._send_json(library.list_papers(pid))
            if len(parts) == 3:
                return self._send_json(library.paper_detail(pid, parts[2]))
            if len(parts) == 5 and parts[3] == "figures":
                body, content_type = library.figure(pid, parts[2], int(parts[4]))
                return self._send_bytes(body, content_type)
            return self._error(404, "not found")
        if tail == "kg":
            self._project_or_404(pid)
            return self._send_json(data.kg_stats(pid))
        if tail == "lane":
            self._project_or_404(pid)
            return self._send_json(data.kg_lane(pid))
        if tail == "attachments":
            self._project_or_404(pid)
            return self._send_json({"attachments": attachments.listing(pid)})
        if tail == "jobs":
            self._project_or_404(pid)
            if len(parts) == 2:
                return self._send_json({"jobs": jobs.list_jobs(pid)})
            job_id = parts[2]
            if len(parts) == 3:
                frm = int((qs.get("from") or ["0"])[0] or 0)
                return self._send_json({"job": jobs.get_job(pid, job_id),
                                        "events": jobs.events(pid, job_id, from_line=frm)})
            if parts[3] == "log":
                return self._send_json({"log": jobs.log_tail(pid, job_id)})
            if parts[3] == "stream":
                return self._stream_job(pid, job_id, qs)
        return self._error(404, "not found")

    def _projects_post(self, path: str, payload: dict):
        rest = path[len("/api/projects"):].strip("/")
        if not rest:
            rec = projects.create(str(payload.get("name", "")),
                                  str(payload.get("description", "")),
                                  payload.get("spec"))
            return self._send_json(rec, status=201)
        parts = [unquote(p) for p in rest.split("/")]
        pid = parts[0]
        self._project_or_404(pid)
        if len(parts) == 1:
            return self._send_json(projects.update(pid, payload))
        tail = parts[1]
        if tail == "papers":
            if len(parts) == 3 and parts[2] == "add":
                return self._send_json(membership.add_dois(pid, payload.get("dois")), status=202)
            if len(parts) == 4 and parts[3] == "remove":
                return self._send_json(membership.remove_paper(pid, parts[2]))
        if tail == "jobs" and len(parts) == 4 and parts[3] == "retry":
            return self._send_json(membership.retry(pid, parts[2]), status=202)
        if tail == "delete":
            return self._send_json(projects.delete(pid, purge=bool(payload.get("purge"))))
        if tail == "build":
            job = jobs.start_build(pid, mode=str(payload.get("mode", "build")),
                                   dry=bool(payload.get("dry")))
            return self._send_json(job, status=202)
        if tail == "run":
            job = jobs.start_run(pid, goal=str(payload.get("goal", "")),
                                 steps=int(payload.get("steps") or 30))
            return self._send_json(job, status=202)
        if tail == "chat":
            if len(parts) == 2:
                return self._send_json(_run_async(
                    assistant.chat(pid, str(payload.get("message", "")))))
            if parts[2] == "apply":
                return self._send_json(assistant.apply_patch(pid, payload.get("patch") or {}))
        if tail == "jobs" and len(parts) == 4 and parts[3] == "cancel":
            return self._send_json(jobs.cancel(pid, parts[2]))
        if tail == "attachments" and len(parts) == 4 and parts[3] == "delete":
            return self._send_json(membership.remove_attachment(pid, parts[2]))
        return self._error(404, "not found")

    def _upload(self, path: str):
        """Raw-body upload: the filename rides in X-Filename, the bytes are the body. Not multipart: a
        single-file drop needs exactly one name and one blob."""
        suffix = "/papers/upload" if path.endswith("/papers/upload") else "/attachments"
        pid = unquote(path[len("/api/projects/"):-len(suffix)])
        try:
            self._project_or_404(pid)
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return self._error(400, "empty upload")
            if length > attachments.MAX_BYTES:
                return self._error(413, f"file too large (max {attachments.MAX_BYTES // 10**6} MB)")
            filename = unquote(self.headers.get("X-Filename", "") or "upload.txt")
            body = self.rfile.read(length)
            if suffix == "/papers/upload":
                return self._send_json(membership.add_upload(pid, filename, body), status=202)
            with membership.project_lease(pid):
                membership.assert_idle(pid)
                return self._send_json(attachments.add(pid, filename, body), status=201)
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except ValueError as exc:
            return self._error(400, str(exc))
        except RuntimeError as exc:
            return self._error(409, str(exc))
        except Exception as exc:
            traceback.print_exc()
            return self._error(500, f"{type(exc).__name__}: {exc}")

    def _stream_job(self, pid: str, job_id: str, qs: dict):
        """SSE over a build's progress file — the same shape as the run-trace stream above, so the
        browser reuses one EventSource idiom for both."""
        from_line = int((qs.get("from") or ["0"])[0] or 0)
        resume = self.headers.get("Last-Event-ID")
        if resume and resume.isdigit():
            from_line = int(resume)
        try:
            jobs.get_job(pid, job_id)
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        for lineno, ev in jobs.tail(pid, job_id, from_line=from_line):
            name = "heartbeat" if ev.get("_heartbeat") else "progress"
            self._write_chunk(
                f"id: {lineno}\nevent: {name}\ndata: {json.dumps(_json_safe(ev))}\n\n".encode("utf-8"))
        self._write_chunk(b"event: end\ndata: {}\n\n")

    # -- static ------------------------------------------------------------

    def _serve_frontend(self, rel: str):
        root = FRONTEND.resolve()
        target = (root / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            if rel == "index.html":
                return self._error(503, "Frontend not built. Run npm ci && npm run build in frontend/.")
            return self._error(404, "not found")
        return self._send_bytes(target.read_bytes(), _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

    def _serve_static(self, rel: str):
        # Prevent path traversal: resolve under STATIC and verify containment.
        target = (STATIC / rel).resolve()
        if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
            return self._error(404, "not found")
        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send_bytes(target.read_bytes(), ctype)

    # -- api: runs ---------------------------------------------------------

    def _run_detail(self, run_id: str):
        if not data.RUN_ID_RE.match(run_id):
            return self._error(400, "bad run id")
        try:
            return self._send_json(data.parse_run(run_id))
        except FileNotFoundError:
            return self._error(404, "run not found")

    def _events(self, run_id: str):
        """The whole investigation as one ordered, timestamped event list — what the player replays."""
        if not data.RUN_ID_RE.match(run_id):
            return self._error(400, "bad run id")
        try:
            return self._send_json(data.run_events(run_id))
        except FileNotFoundError:
            return self._error(404, "run not found")

    def _tree(self, run_id: str):
        """The same investigation as a tree of experiments rather than a timeline: one node per experiment,
        joined by the fan (a step's sibling experiments) and the fork (an agent's child agents)."""
        if not data.RUN_ID_RE.match(run_id):
            return self._error(400, "bad run id")
        try:
            return self._send_json(data.run_tree(run_id))
        except FileNotFoundError:
            return self._error(404, "run not found")

    def _stream_run(self, run_id: str, qs: dict):
        if not data.RUN_ID_RE.match(run_id):
            return self._error(400, "bad run id")
        # Resume point: Last-Event-ID (set by the browser on auto-reconnect)
        # wins over the initial ?from= so reconnects don't replay steps.
        from_line = int((qs.get("from") or ["0"])[0] or 0)
        resume = self.headers.get("Last-Event-ID")
        if resume and resume.isdigit():
            from_line = int(resume)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        # An open-ended stream under HTTP/1.1 has no Content-Length, so it must
        # be framed with chunked transfer encoding or clients block on framing.
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # defeat proxy buffering
        self.end_headers()
        for lineno, item in data.tail_run(run_id, from_line=from_line):
            event = "heartbeat" if item.get("_heartbeat") else "step"
            payload = (
                f"id: {lineno}\nevent: {event}\ndata: {json.dumps(_json_safe(item))}\n\n"
            ).encode("utf-8")
            self._write_chunk(payload)
        self._write_chunk(b"event: end\ndata: {}\n\n")

    def _write_chunk(self, payload: bytes):
        """Write one HTTP chunk (size in hex, CRLF, data, CRLF)."""
        self.wfile.write(f"{len(payload):X}\r\n".encode("ascii"))
        self.wfile.write(payload)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    # -- api: kg -----------------------------------------------------------

    def _kg(self, qs: dict):
        claim_id = (qs.get("claim") or [""])[0]
        if claim_id:
            source = (qs.get("source") or [""])[0]
            if not source:
                return self._error(400, "claim inspection requires a collection source")
            try:
                return self._send_json(evidence.claim_detail(source, claim_id))
            except KeyError as exc:
                return self._error(404, exc.args[0])
        srcs = list(data.kg_sources().keys())
        if not srcs:
            return self._send_json({"nodes": [], "edges": [], "sources": []})
        source = (qs.get("source") or [srcs[0]])[0]
        try:
            limit = int((qs.get("limit") or ["220"])[0])
        except ValueError:
            return self._error(400, "limit must be an integer")
        pick = lambda key: (qs.get(key) or [None])[0]          # noqa: E731
        try:
            return self._send_json(data.kg_graph(
                source, limit=limit, status=pick("status"), q=pick("q"), polarity=pick("polarity"),
                kind=pick("kind"), relation_class=pick("relation_class"), predicate=pick("predicate"),
            ))
        except KeyError:
            return self._error(404, "unknown kg source")


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print(f"  engine UI  →  http://{host}:{port}")
    print(f"  serving state from {data.PROCESSED}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down")
        httpd.shutdown()

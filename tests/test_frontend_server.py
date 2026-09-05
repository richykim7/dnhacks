"""Frontend integration contracts. No model calls or live project mutations."""
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import duckdb
import pytest

from dnhacksbio.webui import data, server


@pytest.fixture
def http(monkeypatch, tmp_path):
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text('<div id="root"></div>')
    (build / "assets" / "app.js").write_text('console.log("workspace")')
    (tmp_path / "dist-secret").mkdir()
    (tmp_path / "dist-secret" / "secret.js").write_text('private')
    monkeypatch.setattr(server, "FRONTEND", build)
    monkeypatch.setattr(server, "STATIC", build)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_port, build
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def get(http, path):
    conn = HTTPConnection("127.0.0.1", http[0], timeout=3)
    conn.request("GET", path)
    response = conn.getresponse()
    status, content_type, body = response.status, response.getheader("Content-Type"), response.read()
    conn.close()
    return status, content_type, body


def test_built_frontend_and_assets(http):
    assert get(http, "/")[0] == 200
    assert b'id="root"' in get(http, "/")[2]
    assert get(http, "/assets/app.js")[:2] == (200, "text/javascript; charset=utf-8")


def test_missing_build_is_actionable(http):
    (http[1] / "index.html").unlink()
    status, _, body = get(http, "/")
    assert status == 503
    assert "npm" in json.loads(body)["error"]


@pytest.mark.parametrize("path", ["/assets/../../dist-secret/secret.js", "/assets/%2e%2e/%2e%2e/dist-secret/secret.js", "/static/../dist-secret/secret.js", "/.env"])
def test_static_paths_cannot_escape_build(http, path):
    assert get(http, path)[0] == 404


def test_stream_nonfinite_numbers_are_valid_json(monkeypatch):
    handler = object.__new__(server.Handler)
    handler.headers = {}
    handler.send_response = lambda *a: None
    handler.send_header = lambda *a: None
    handler.end_headers = lambda: None
    chunks = []
    handler._write_chunk = chunks.append
    monkeypatch.setattr(data, "tail_run", lambda *a, **k: iter([(1, {"action": "note", "effect": float("nan"), "nested": [float("inf")]})]))
    handler._stream_run("recorded", {})
    payload = chunks[0].decode().split("data: ", 1)[1].strip()
    assert json.loads(payload) == {"action": "note", "effect": None, "nested": [None]}


def test_experiment_evidence_and_query_errors_are_exposed(monkeypatch, tmp_path):
    db = tmp_path / "kg.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table exploration(entry_id integer, run_id varchar, kind varchar, title varchar, body varchar, status varchar, score double, provenance varchar, code varchar, result varchar, created_at varchar)")
    con.execute("insert into exploration values (1, 'recorded', 'experiment', 'An analysis', 'Its rationale', 'open', NULL, ?, 'fit(samples)', ?, '2026-09-05')", [json.dumps({"dataset": "fixture"}), json.dumps({"effect": .4, "p_null": .02})])
    con.close()
    monkeypatch.setattr(data, "tree_runs", lambda _: ["recorded"])
    monkeypatch.setattr(data, "_db_for_run", lambda _: db)
    monkeypatch.setattr(data, "_fans", lambda _: ({}, []))
    monkeypatch.setattr(data, "_fork_index_for", lambda _: [])
    node = data.run_tree("recorded")["nodes"][0]
    assert node["body"] == "Its rationale"
    assert node["code"] == "fit(samples)"
    assert node["result"]["effect"] == .4
    assert node["provenance"]["dataset"] == "fixture"
    con = duckdb.connect(str(db))
    con.execute("alter table exploration drop column result")
    con.close()
    assert data.run_tree("recorded")["db_unreadable"]

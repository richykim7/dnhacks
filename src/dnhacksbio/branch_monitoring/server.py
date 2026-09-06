"""Separate authenticated operator service. No routes are added to the research API."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


def make_server(store, token, host="127.0.0.1", port=8804):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Separate operator token required")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def reply(self, status, value, content_type="application/json"):
            body = json.dumps(value, allow_nan=False).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token)

        def do_GET(self):
            path = urlparse(self.path).path
            assets = {"/": ("operator.html", "text/html; charset=utf-8"),
                      "/operator.js": ("operator.js", "text/javascript; charset=utf-8"),
                      "/operator.css": ("operator.css", "text/css; charset=utf-8")}
            if path in assets:
                filename, mime = assets[path]
                return self.reply(200, (Path(__file__).parent / filename).read_bytes(), mime)
            if not self.authorized():
                return self.reply(401, {"error": "Operator authorization required"})
            try:
                if path == "/api/episodes":
                    return self.reply(200, {"episodes": [{**e, "history": store.checkpoints(e["episode_id"])} for e in store.episodes()]})
                if path.startswith("/api/reviews/"):
                    return self.reply(200, {"reviews": store.reviews(unquote(path[len('/api/reviews/'):]))})
                return self.reply(404, {"error": "Unavailable"})
            except Exception:
                return self.reply(400, {"error": "Operator record unavailable"})

        def do_POST(self):
            self.connection.settimeout(15)
            if not self.authorized():
                return self.reply(401, {"error": "Operator authorization required"})
            if self.path != "/api/review":
                return self.reply(404, {"error": "Unavailable"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 20000:
                    raise ValueError("Invalid size")
                body = json.loads(self.rfile.read(length))
                record = store.review(body["review_id"], body["decision"], body["note"])
                return self.reply(200, record)
            except Exception:
                return self.reply(400, {"error": "Review requires a valid record, decision and written note"})

    return ThreadingHTTPServer((host, port), Handler)

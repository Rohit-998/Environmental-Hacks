"""Local dev server: the same API as the Lambda, backed by an in-memory store.

    uv run python -m airday.devserver            # http://localhost:8000
    ADMIN_KEY=dev uv run python -m airday.devserver

Standard library only. Not for production.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import api
from .store import MemoryStore

STORE = MemoryStore()
ALLOWED_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
EXTRA_ROUTES: dict = {}

try:  # chat and translation are optional (need the agent extra and a model provider)
    from . import agent

    EXTRA_ROUTES = agent.ROUTES
except Exception:  # pragma: no cover
    pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "content-type, x-admin-key, x-dev-user, authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802
        self._send(204, {})

    def _claims(self) -> dict | None:
        """Local stand-in for the Cognito JWT authorizer: `x-dev-user: <sub>` acts as a signed-in user.
        Dev server only; the deployed API verifies real tokens at API Gateway."""
        sub = self.headers.get("x-dev-user")
        return {"sub": sub} if sub else None

    def _handle(self, method: str) -> None:
        url = urllib.parse.urlparse(self.path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else None
        status, out = api.route(method, url.path, query, body, dict(self.headers), STORE, EXTRA_ROUTES,
                                claims=self._claims())
        self._send(status, out)

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_PUT(self):  # noqa: N802
        self._handle("PUT")

    def do_POST(self):  # noqa: N802
        self._handle("POST")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", "8000"))
    os.environ.setdefault("ADMIN_KEY", "dev")
    print(f"AirDay dev API on http://localhost:{port} (admin key: {os.environ['ADMIN_KEY']})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

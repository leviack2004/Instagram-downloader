from __future__ import annotations

import json
import logging
import mimetypes
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Deque

from instagram_adapter import InstagramAdapterError, normalize_instagram_url, resolve_instagram_media

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
TEMPLATES_DIR = ROOT / "templates"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    window_seconds: int = 60
    max_requests: int = 15


class InMemoryRateLimiter:
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests_by_ip: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, ip: str) -> bool:
        now = time.time()
        timestamps = self.requests_by_ip[ip]
        while timestamps and now - timestamps[0] > self.config.window_seconds:
            timestamps.popleft()
        if len(timestamps) >= self.config.max_requests:
            return False
        timestamps.append(now)
        return True


rate_limiter = InMemoryRateLimiter(RateLimitConfig())


class AppHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, status: int = 200):
        if not file_path.exists():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        self.send_response(status)
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == "/":
            self._send_file(TEMPLATES_DIR / "index.html")
            return
        if self.path.startswith("/static/"):
            rel = self.path.removeprefix("/static/")
            self._send_file(STATIC_DIR / rel)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/resolve":
            self.send_error(404)
            return

        ip = self.client_address[0]
        if not rate_limiter.allow(ip):
            self._send_json(
                {
                    "error": "rate_limited",
                    "message": "Too many requests. Please wait a minute and try again.",
                    "next_step": "Retry shortly.",
                },
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length) or b"{}")
        except json.JSONDecodeError:
            payload = {}

        raw_url = (payload.get("url") or "").strip()
        if not raw_url:
            self._send_json(
                {
                    "error": "invalid_url",
                    "message": "Please provide an Instagram URL.",
                    "next_step": "Paste a public post, reel, or tv link.",
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            normalized = normalize_instagram_url(raw_url)
            result = resolve_instagram_media(normalized)
            logger.info("resolve_success content_type=%s items=%s", result.content_type, len(result.items))
            self._send_json(result.to_dict())
        except InstagramAdapterError as err:
            logger.info("resolve_failed error=%s url=%s", err.code, raw_url)
            status = {
                "invalid_url": HTTPStatus.BAD_REQUEST,
                "unsupported_content": HTTPStatus.BAD_REQUEST,
                "private_or_unavailable": HTTPStatus.NOT_FOUND,
                "upstream_rate_limited": HTTPStatus.TOO_MANY_REQUESTS,
                "upstream_failure": HTTPStatus.BAD_GATEWAY,
            }.get(err.code, HTTPStatus.BAD_GATEWAY)
            self._send_json({"error": err.code, "message": err.message, "next_step": err.next_step}, status)


def run_server():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    logger.info("Serving on http://0.0.0.0:%s", port)
    server.serve_forever()


if __name__ == "__main__":
    run_server()

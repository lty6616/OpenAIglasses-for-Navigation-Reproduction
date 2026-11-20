# -*- coding: utf-8 -*-
"""Serve the project directory for static UI previews without FastAPI deps."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview static pages from the project root.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    handler = functools.partial(QuietHandler, directory=str(ROOT))
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"[PREVIEW] http://{args.host}:{args.port}/templates/imu.html", flush=True)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

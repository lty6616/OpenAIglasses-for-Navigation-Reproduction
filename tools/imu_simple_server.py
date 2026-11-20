# -*- coding: utf-8 -*-
"""Dependency-free ICM42688 upper-computer server.

It serves the IMU dashboard, receives UDP JSON on port 12345, and exposes
`/api/imu/latest` for browser polling. It does not require FastAPI.
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import socket
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
G = 9.80665
history: deque[dict[str, Any]] = deque(maxlen=1200)
latest: dict[str, Any] | None = None
lock = threading.Lock()

last_ts_ms = 0.0
yaw = 0.0
roll_f = 0.0
pitch_f = 0.0
yaw_f = 0.0


def wrap180(value: float) -> float:
    out = value % 360.0
    if out >= 180.0:
        out -= 360.0
    if out < -180.0:
        out += 360.0
    return out


def v3(value: Any) -> dict[str, float]:
    src = value if isinstance(value, dict) else {}
    return {
        "x": float(src.get("x", 0.0) or 0.0),
        "y": float(src.get("y", 0.0) or 0.0),
        "z": float(src.get("z", 0.0) or 0.0),
    }


def motion_label(roll: float, pitch: float, accel_norm: float, gyro_norm: float, still: bool) -> str:
    if still:
        return "still"
    if abs(accel_norm - G) > 4.0:
        return "impact"
    if abs(roll) > 45.0 or abs(pitch) > 45.0:
        return "tilted"
    if gyro_norm > 90.0:
        return "rotating"
    return "moving"


def process_packet(raw: dict[str, Any]) -> dict[str, Any]:
    global latest, last_ts_ms, yaw, roll_f, pitch_f, yaw_f

    ts_ms = float(raw.get("ts") or raw.get("timestamp_ms") or time.time() * 1000.0)
    if last_ts_ms <= 0 or ts_ms <= last_ts_ms or (ts_ms - last_ts_ms) > 3000:
        dt = 0.02
    else:
        dt = (ts_ms - last_ts_ms) / 1000.0
    last_ts_ms = ts_ms

    accel = v3(raw.get("accel") or {"x": raw.get("ax"), "y": raw.get("ay"), "z": raw.get("az")})
    gyro = v3(raw.get("gyro") or {"x": raw.get("gx"), "y": raw.get("gy"), "z": raw.get("gz")})

    ax, ay, az = accel["x"], accel["y"], accel["z"]
    gx, gy, gz = gyro["x"], gyro["y"], gyro["z"]
    roll = math.atan2(az, ay) * 180.0 / math.pi
    pitch = math.atan2(-ax, math.hypot(ay, az)) * 180.0 / math.pi
    accel_norm = math.hypot(math.hypot(ax, ay), az)
    gyro_norm = math.hypot(math.hypot(gx, gy), gz)
    still = abs(accel_norm - G) < 0.45 and gyro_norm < 0.4

    yawdot = gy
    if abs(yawdot) < 0.08 or still:
        yawdot = 0.0
    yaw = wrap180(yaw + yawdot * dt)

    roll_f = 0.15 * roll + 0.85 * roll_f
    pitch_f = 0.15 * pitch + 0.85 * pitch_f
    yaw_f = 0.15 * yaw + 0.85 * yaw_f

    item = {
        "ts": ts_ms,
        "server_time": time.time(),
        "dt": dt,
        "temp_c": raw.get("temp_c"),
        "angles": {"roll": roll_f, "pitch": pitch_f, "yaw": yaw_f},
        "accel": accel,
        "gyro": gyro,
        "metrics": {
            "accel_norm": accel_norm,
            "gyro_norm": gyro_norm,
            "still": still,
            "near_flat": abs(roll_f) < 2.0 and abs(pitch_f) < 2.0,
            "gravity": G,
        },
        "state": {
            "motion": motion_label(roll_f, pitch_f, accel_norm, gyro_norm, still),
            "still": still,
            "near_flat": abs(roll_f) < 2.0 and abs(pitch_f) < 2.0,
        },
        "raw": raw,
    }
    with lock:
        latest = item
        history.append(item)
    return item


def udp_loop(host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"[IMU] UDP listening on {host}:{port}", flush=True)
    while True:
        data, _addr = sock.recvfrom(4096)
        try:
            raw = json.loads(data.decode("utf-8", errors="ignore").strip())
            process_packet(raw)
        except Exception:
            continue


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def send_bytes(self, data: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, value: Any) -> None:
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/imu"):
            self.send_bytes((ROOT / "templates" / "imu.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self.send_bytes(b"OK", "text/plain; charset=utf-8")
            return
        if path == "/api/imu/latest":
            with lock:
                value = latest or {"status": "no_data"}
            self.send_json(value)
            return
        if path == "/api/imu/log":
            query = parse_qs(parsed.query)
            limit = max(1, min(int(query.get("limit", ["300"])[0]), 1200))
            with lock:
                items = list(history)[-limit:]
            self.send_json({"count": len(items), "items": items})
            return
        if path.startswith("/static/"):
            rel = path.removeprefix("/static/")
            target = (ROOT / "static" / rel).resolve()
            static_root = (ROOT / "static").resolve()
            if static_root not in target.parents and target != static_root:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.exists() or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_bytes(target.read_bytes(), ctype)
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a dependency-free IMU web upper-computer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--udp-host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=12345)
    args = parser.parse_args()

    threading.Thread(target=udp_loop, args=(args.udp_host, args.udp_port), daemon=True).start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[IMU] page: http://127.0.0.1:{args.port}/imu", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

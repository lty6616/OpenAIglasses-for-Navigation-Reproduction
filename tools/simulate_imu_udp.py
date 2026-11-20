# -*- coding: utf-8 -*-
"""Send synthetic ICM42688-like IMU packets to the server UDP port."""

from __future__ import annotations

import argparse
import json
import math
import socket
import time


def packet_at(start: float) -> dict:
    now = time.time()
    t = now - start
    return {
        "ts": int(now * 1000),
        "accel": {
            "x": math.sin(t * 1.4) * 0.45,
            "y": 9.80665 + math.sin(t * 1.8) * 0.18,
            "z": math.sin(t * 1.1 + 1.2) * 0.55,
        },
        "gyro": {
            "x": math.cos(t * 1.2) * 32.0,
            "y": math.sin(t * 1.6) * 18.0,
            "z": 24.0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate ESP32 UDP IMU packets.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=12345)
    parser.add_argument("--hz", type=float, default=50.0)
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()

    period = 1.0 / max(args.hz, 1.0)
    deadline = time.time() + args.seconds
    start = time.time()
    count = 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[SIM-IMU] sending to {args.host}:{args.port} at {args.hz:g} Hz for {args.seconds:g}s")
    try:
        while time.time() < deadline:
            payload = json.dumps(packet_at(start), separators=(",", ":")).encode("utf-8")
            sock.sendto(payload, (args.host, args.port))
            count += 1
            time.sleep(period)
    finally:
        sock.close()
    print(f"[SIM-IMU] sent {count} packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

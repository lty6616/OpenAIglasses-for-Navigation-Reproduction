# -*- coding: utf-8 -*-
"""Verify the live YOLOE + ByteTrack monitor while a camera source is active.

Start a real ESP32 stream or simulate a video first, then run:
    python tools/verify_traffic_monitor.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.request

import cv2
import numpy as np
import websockets


def request_json(base_url: str, path: str, method: str = "GET") -> dict:
    request = urllib.request.Request(base_url + path, method=method)
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read())


async def verify(host: str, port: int, timeout: float) -> bool:
    base_url = f"http://{host}:{port}"
    started = request_json(base_url, "/api/traffic-monitor/start", "POST")
    print(f"[1] monitor start -> {started['state']}")

    deadline = time.monotonic() + timeout
    received = None
    uri = f"ws://{host}:{port}/ws/traffic_viewer"
    async with websockets.connect(uri, max_size=None) as websocket:
        while time.monotonic() < deadline:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                state = request_json(base_url, "/api/status")["traffic_monitor"]
                print(f"    waiting: state={state['state']} frames={state['processed_frames']}")
                if state["state"] == "error":
                    print(f"[2] monitor error: {state['error']}")
                    return False
                continue
            if isinstance(message, bytes):
                received = message
                break

    if received is None:
        print("[2] no AI JPEG received; make sure ESP32/video simulator is streaming")
        return False
    image = cv2.imdecode(np.frombuffer(received, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        print("[2] traffic WebSocket returned invalid JPEG")
        return False
    print(f"[2] AI JPEG OK -> {image.shape[1]}x{image.shape[0]}, {len(received)} bytes")

    status = request_json(base_url, "/api/status")
    monitor = status["traffic_monitor"]
    print(
        "[3] status -> "
        f"state={monitor['state']} frames={monitor['processed_frames']} "
        f"inference={monitor['inference_ms']}ms fps={monitor['processing_fps']} "
        f"counts={monitor['counts']}"
    )
    valid = monitor["state"] == "running" and monitor["processed_frames"] > 0
    print("\n=== TRAFFIC MONITOR:", "PASS" if valid else "FAIL", "===")
    return valid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(verify(args.host, args.port, args.timeout)) else 1)


if __name__ == "__main__":
    main()

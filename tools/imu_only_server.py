# -*- coding: utf-8 -*-
"""Minimal ICM42688 upper-computer server.

This avoids importing the full vision/audio project. Use it when you only want
to receive IMU UDP packets and view them in the browser.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


ROOT = Path(__file__).resolve().parents[1]
G = 9.80665
GRAV_BETA = 0.98
STILL_W = 0.4
A_TOL = 0.45
ANG_EMA = 0.15
YAW_DB = 0.08

app = FastAPI(title="ICM42688 IMU Only Server")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

clients: set[WebSocket] = set()
history: deque[dict[str, Any]] = deque(maxlen=1200)
latest: dict[str, Any] | None = None

g_lp = {"x": 0.0, "y": G, "z": 0.0}
g_off = {"x": 0.0, "y": 0.0, "z": 0.0}
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


def v3(value: Any) -> dict[str, float]:
    src = value if isinstance(value, dict) else {}
    return {
        "x": float(src.get("x", 0.0) or 0.0),
        "y": float(src.get("y", 0.0) or 0.0),
        "z": float(src.get("z", 0.0) or 0.0),
    }


def process_packet(raw: dict[str, Any]) -> dict[str, Any]:
    global g_lp, g_off, last_ts_ms, yaw, roll_f, pitch_f, yaw_f, latest

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

    g_lp["x"] = GRAV_BETA * g_lp["x"] + (1.0 - GRAV_BETA) * ax
    g_lp["y"] = GRAV_BETA * g_lp["y"] + (1.0 - GRAV_BETA) * ay
    g_lp["z"] = GRAV_BETA * g_lp["z"] + (1.0 - GRAV_BETA) * az
    gmag = math.hypot(math.hypot(g_lp["x"], g_lp["y"]), g_lp["z"]) or 1.0
    ghat = {"x": g_lp["x"] / gmag, "y": g_lp["y"] / gmag, "z": g_lp["z"] / gmag}

    roll = math.atan2(az, ay) * 180.0 / math.pi
    pitch = math.atan2(-ax, math.hypot(ay, az)) * 180.0 / math.pi
    accel_norm = math.hypot(math.hypot(ax, ay), az)
    gyro_norm = math.hypot(math.hypot(gx, gy), gz)
    still = abs(accel_norm - G) < A_TOL and gyro_norm < STILL_W

    if still:
        g_off["x"] = 0.995 * g_off["x"] + 0.005 * gx
        g_off["y"] = 0.995 * g_off["y"] + 0.005 * gy
        g_off["z"] = 0.995 * g_off["z"] + 0.005 * gz

    yawdot = (
        (gx - g_off["x"]) * ghat["x"]
        + (gy - g_off["y"]) * ghat["y"]
        + (gz - g_off["z"]) * ghat["z"]
    )
    if abs(yawdot) < YAW_DB or still:
        yawdot = 0.0
    yaw = wrap180(yaw + yawdot * dt)

    roll_f = ANG_EMA * roll + (1.0 - ANG_EMA) * roll_f
    pitch_f = ANG_EMA * pitch + (1.0 - ANG_EMA) * pitch_f
    yaw_f = ANG_EMA * yaw + (1.0 - ANG_EMA) * yaw_f

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
    }
    latest = item
    history.append(item)
    return item


async def broadcast(item: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    text = json.dumps(item, ensure_ascii=False)
    for ws in list(clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


class UDPProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr) -> None:
        try:
            raw = json.loads(data.decode("utf-8", errors="ignore").strip())
            item = process_packet(raw)
            asyncio.create_task(broadcast(item))
        except Exception:
            return


@app.get("/", response_class=HTMLResponse)
@app.get("/imu", response_class=HTMLResponse)
def imu_page() -> HTMLResponse:
    return HTMLResponse((ROOT / "templates" / "imu.html").read_text(encoding="utf-8"))


@app.get("/api/health", response_class=PlainTextResponse)
def health() -> str:
    return "OK"


@app.get("/api/imu/latest")
def imu_latest() -> dict[str, Any]:
    return latest or {"status": "no_data"}


@app.get("/api/imu/log")
def imu_log(limit: int = 300) -> dict[str, Any]:
    limit = max(1, min(limit, 1200))
    return {"count": min(limit, len(history)), "items": list(history)[-limit:]}


@app.websocket("/ws")
async def ws_imu(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the IMU-only web upper-computer.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--udp-host", default="0.0.0.0")
    parser.add_argument("--udp-port", type=int, default=12345)
    args = parser.parse_args()

    @app.on_event("startup")
    async def startup() -> None:
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(lambda: UDPProtocol(), local_addr=(args.udp_host, args.udp_port))
        print(f"[IMU] UDP listening on {args.udp_host}:{args.udp_port}")
        print(f"[IMU] page: http://127.0.0.1:{args.port}/imu")

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

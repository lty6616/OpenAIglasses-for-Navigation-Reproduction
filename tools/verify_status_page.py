# -*- coding: utf-8 -*-
"""验证 /status 监控页的数据链路（不依赖浏览器）：
1. /api/health 返回 OK
2. /api/status JSON 字段齐全，摄像头/IMU 年龄随模拟器变化
3. 模拟摄像头推流期间 /ws/viewer 能收到二进制 JPEG 帧
用法: python tools/verify_status_page.py --host 127.0.0.1 --port 8081
"""
import argparse
import asyncio
import json
import time
import urllib.request

import websockets


def http_json(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.read()


async def check(base, host, port):
    ok = True

    # 1. health
    try:
        health = http_json(base, "/api/health").decode()
        print(f"[1] /api/health -> {health!r}", "OK" if health.strip() == "OK" else "FAIL")
        ok &= health.strip() == "OK"
    except Exception as e:
        print(f"[1] /api/health FAIL: {e}")
        return False

    # 2. /api/status 字段
    try:
        d = json.loads(http_json(base, "/api/status"))
        required = [
            "server_time", "uptime_sec", "camera_esp32_connected",
            "audio_esp32_connected", "viewer_count", "ui_client_count",
            "imu_client_count", "last_frame_age_ms", "last_imu_age_ms",
            "navigation_active", "yolomedia_running",
            "demo_stream_active", "traffic_viewer_count", "traffic_monitor",
        ]
        missing = [k for k in required if k not in d]
        print(f"[2] /api/status 字段缺失: {missing}" if missing else f"[2] /api/status 字段齐全 OK")
        print(f"    camera_esp32={d['camera_esp32_connected']} viewer={d['viewer_count']} last_frame_age={d['last_frame_age_ms']}")
        ok &= not missing
    except Exception as e:
        print(f"[2] /api/status FAIL: {e}")
        return False

    # 3. 模拟器运行时 /ws/viewer 应收到二进制帧
    #    若模拟器未运行，此项提示跳过（不算失败）
    try:
        before = json.loads(http_json(base, "/api/status"))
        t0 = time.time()
        got_frame = False
        async with websockets.connect(f"ws://{host}:{port}/ws/viewer", max_size=2**22) as ws:
            while time.time() - t0 < 6:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    if isinstance(msg, (bytes, bytearray)) and len(msg) > 100:
                        got_frame = True
                        break
                except asyncio.TimeoutError:
                    pass
        after = json.loads(http_json(base, "/api/status"))
        sim_active = (after["last_frame_age_ms"] or 1e9) < 3000
        if got_frame:
            print(f"[3] /ws/viewer 收到 JPEG 帧（{len(msg)} 字节）OK")
        elif sim_active:
            print("[3] /api/status 显示帧流活跃但 viewer 未收到帧 FAIL")
            ok = False
        else:
            print("[3] 无帧流（模拟器未运行），跳过 viewer 测试（运行 simulate_camera_client.py 后重试）")
    except Exception as e:
        print(f"[3] /ws/viewer FAIL: {e}")
        ok = False

    return ok


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8081)
    args = ap.parse_args()
    base = f"http://{args.host}:{args.port}"
    ok = await check(base, args.host, args.port)
    print("\n=== 验证结果:", "PASS" if ok else "FAIL", "===")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())

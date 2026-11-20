# -*- coding: utf-8 -*-
"""Send JPEG frames to /ws/camera without ESP32 hardware."""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import cv2
import numpy as np
import websockets


def make_frame(width: int, height: int, index: int) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :, 0] = (index * 7) % 255
    img[:, :, 1] = np.linspace(0, 255, width, dtype=np.uint8)
    img[:, :, 2] = np.linspace(255, 0, height, dtype=np.uint8)[:, None]
    cv2.putText(img, f"SIM FRAME {index}", (30, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("Failed to encode generated frame")
    return buf.tobytes()


def load_image(path: Path) -> bytes:
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"Cannot read image: {path}")
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError(f"Cannot encode image: {path}")
    return buf.tobytes()


def fit_frame(img: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    height, width = img.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale >= 1.0:
        return img
    return cv2.resize(
        img,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def encode_frame(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("Failed to encode video frame")
    return buf.tobytes()


async def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--image", type=Path, help="Optional image to send repeatedly")
    parser.add_argument("--video", type=Path, help="Optional traffic video to stream frame by frame")
    parser.add_argument("--loop", action="store_true", help="Loop the video until --seconds expires")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    if args.image and args.video:
        parser.error("--image and --video cannot be used together")
    if args.fps <= 0:
        parser.error("--fps must be greater than zero")
    if args.seconds < 0:
        parser.error("--seconds cannot be negative")

    uri = f"ws://{args.host}:{args.port}/ws/camera"
    interval = 1.0 / max(args.fps, 0.1)
    end_at = time.monotonic() + args.seconds if args.seconds > 0 else None
    static_frame = load_image(args.image) if args.image else None
    capture = None
    if args.video:
        capture = cv2.VideoCapture(str(args.video))
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open video: {args.video}")

    print(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri, max_size=None) as ws:
            index = 0
            next_frame_at = time.monotonic()
            while end_at is None or time.monotonic() < end_at:
                if capture is not None:
                    ok, image = capture.read()
                    if not ok:
                        if not args.loop:
                            break
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, image = capture.read()
                        if not ok:
                            break
                    image = fit_frame(image, args.width, args.height)
                    frame = encode_frame(image)
                else:
                    frame = static_frame or make_frame(args.width, args.height, index)
                await ws.send(frame)
                index += 1
                next_frame_at += interval
                await asyncio.sleep(max(0.0, next_frame_at - time.monotonic()))
    finally:
        if capture is not None:
            capture.release()
    print(f"Sent {index} frames")


if __name__ == "__main__":
    asyncio.run(run())

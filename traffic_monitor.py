# -*- coding: utf-8 -*-
"""Latest-frame traffic monitoring with YOLOE and ByteTrack.

The worker is deliberately independent from the navigation state machine. Camera
ingestion only replaces a one-item queue, so slow inference cannot build latency
or block the ESP32 WebSocket.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from collections import Counter
from typing import Any, Callable, Dict, Optional

import cv2
import numpy as np
import torch

from obstacle_detector_client import gpu_infer_slot
from yoloe_backend import YoloEBackend


TRAFFIC_CLASSES = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]
CLASS_COLORS = {
    "person": (93, 242, 165),
    "bicycle": (91, 216, 255),
    "car": (110, 168, 254),
    "motorcycle": (255, 209, 102),
    "bus": (255, 140, 90),
    "truck": (255, 107, 107),
}


class TrafficMonitor:
    """Run traffic inference on a bounded latest-frame queue."""

    def __init__(self) -> None:
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._frame_callback: Optional[Callable[[bytes], None]] = None
        self._state: Dict[str, Any] = {
            "state": "idle",
            "message": "未启动",
            "model_loaded": False,
            "processed_frames": 0,
            "dropped_frames": 0,
            "inference_ms": None,
            "processing_fps": 0.0,
            "last_result_age_ms": None,
            "counts": {},
            "detections": [],
            "error": None,
        }
        self._last_result_time = 0.0

    def set_frame_callback(self, callback: Callable[[bytes], None]) -> None:
        self._frame_callback = callback

    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self._snapshot_locked()
            self._stop_event.clear()
            self._state.update({
                "state": "loading",
                "message": "正在加载 YOLOE",
                "model_loaded": False,
                "processed_frames": 0,
                "dropped_frames": 0,
                "inference_ms": None,
                "processing_fps": 0.0,
                "counts": {},
                "detections": [],
                "error": None,
            })
            self._last_result_time = 0.0
            self._thread = threading.Thread(target=self._run, name="traffic-monitor", daemon=True)
            self._thread.start()
            return self._snapshot_locked()

    def stop(self, wait: bool = False) -> Dict[str, Any]:
        with self._lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                self._state.update({
                    "state": "idle",
                    "message": "未启动",
                    "model_loaded": False,
                    "processed_frames": 0,
                    "dropped_frames": 0,
                    "inference_ms": None,
                    "processing_fps": 0.0,
                    "counts": {},
                    "detections": [],
                })
                self._last_result_time = 0.0
                return self._snapshot_locked()
            self._state.update({"state": "stopping", "message": "正在停止"})
            self._stop_event.set()
        if wait:
            thread.join(timeout=5.0)
        return self.snapshot()

    def submit_jpeg(self, jpeg_bytes: bytes) -> bool:
        if not jpeg_bytes:
            return False
        with self._lock:
            running = self._state["state"] in {"loading", "running"}
        if not running:
            return False
        try:
            self._queue.put_nowait(jpeg_bytes)
            return True
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(jpeg_bytes)
            except queue.Full:
                return False
            with self._lock:
                self._state["dropped_frames"] += 1
            return True

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> Dict[str, Any]:
        data = dict(self._state)
        data["counts"] = dict(self._state["counts"])
        data["detections"] = [dict(item) for item in self._state["detections"]]
        if self._last_result_time > 0:
            data["last_result_age_ms"] = int((time.time() - self._last_result_time) * 1000)
        return data

    def _run(self) -> None:
        backend: Optional[YoloEBackend] = None
        try:
            backend = YoloEBackend()
            backend.set_text_classes(TRAFFIC_CLASSES)
            with self._lock:
                self._state.update({
                    "state": "running",
                    "message": "等待视频帧",
                    "model_loaded": True,
                    "processed_frames": 0,
                    "dropped_frames": 0,
                    "inference_ms": None,
                    "processing_fps": 0.0,
                    "counts": {},
                    "detections": [],
                })

            target_fps = max(0.2, float(os.getenv("TRAFFIC_MONITOR_FPS", "5")))
            interval = 1.0 / target_fps
            confidence = float(os.getenv("TRAFFIC_MONITOR_CONF", "0.20"))
            image_size = int(os.getenv("TRAFFIC_MONITOR_IMGSZ", "640"))
            jpeg_quality = int(os.getenv("TRAFFIC_MONITOR_JPEG_QUALITY", "82"))
            previous_finish = 0.0
            last_result_perf = 0.0

            while not self._stop_event.is_set():
                try:
                    jpeg = self._queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                wait_time = interval - (time.perf_counter() - previous_finish)
                if wait_time > 0 and self._stop_event.wait(wait_time):
                    break
                # Use the newest queued frame after throttling.
                try:
                    while True:
                        jpeg = self._queue.get_nowait()
                except queue.Empty:
                    pass

                frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                started = time.perf_counter()
                with gpu_infer_slot():
                    result = backend.segment(
                        frame,
                        conf=confidence,
                        imgsz=image_size,
                        persist=True,
                    )
                inference_ms = (time.perf_counter() - started) * 1000.0
                now_perf = time.perf_counter()
                previous_finish = now_perf

                annotated = self._draw(frame, result)
                ok, encoded = cv2.imencode(
                    ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
                )
                detections = []
                for box, name, track_id, conf in zip(
                    result["boxes"], result["names"], result["ids"], result["confs"]
                ):
                    detections.append({
                        "name": name,
                        "track_id": track_id,
                        "confidence": round(float(conf), 3),
                        "box": None if box is None else [round(float(v), 1) for v in box],
                    })
                counts = Counter(item["name"] for item in detections)

                with self._lock:
                    old_fps = float(self._state["processing_fps"])
                    instant_fps = 0.0 if last_result_perf <= 0 else 1.0 / max(now_perf - last_result_perf, 0.001)
                    last_result_perf = now_perf
                    self._last_result_time = time.time()
                    self._state.update({
                        "state": "running",
                        "message": "识别中",
                        "processed_frames": self._state["processed_frames"] + 1,
                        "inference_ms": round(inference_ms, 1),
                        "processing_fps": round(instant_fps if old_fps == 0 else old_fps * 0.8 + instant_fps * 0.2, 1),
                        "counts": dict(counts),
                        "detections": detections[:30],
                        "error": None,
                    })

                callback = self._frame_callback
                if ok and callback is not None:
                    callback(encoded.tobytes())
        except Exception as exc:
            with self._lock:
                self._state.update({
                    "state": "error",
                    "message": "交通识别启动失败",
                    "model_loaded": False,
                    "error": str(exc),
                })
        finally:
            if backend is not None:
                del backend
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            with self._lock:
                if self._state["state"] != "error":
                    self._state.update({
                        "state": "idle",
                        "message": "未启动",
                        "model_loaded": False,
                        "processed_frames": 0,
                        "dropped_frames": 0,
                        "inference_ms": None,
                        "processing_fps": 0.0,
                        "counts": {},
                        "detections": [],
                    })
                    self._last_result_time = 0.0
                self._thread = None

    @staticmethod
    def _draw(frame: np.ndarray, result: Dict[str, Any]) -> np.ndarray:
        image = frame.copy()
        overlay = image.copy()
        for mask, name in zip(result["masks"], result["names"]):
            color = CLASS_COLORS.get(name, (91, 216, 255))
            overlay[mask.astype(bool)] = color
        image = cv2.addWeighted(overlay, 0.28, image, 0.72, 0)

        for box, name, track_id, conf in zip(
            result["boxes"], result["names"], result["ids"], result["confs"]
        ):
            if box is None:
                continue
            x1, y1, x2, y2 = (int(value) for value in box)
            color = CLASS_COLORS.get(name, (91, 216, 255))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            track = f" #{track_id}" if track_id is not None else ""
            label = f"{name}{track} {conf:.2f}"
            cv2.putText(
                image,
                label,
                (x1, max(22, y1 - 7)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                color,
                2,
                cv2.LINE_AA,
            )
        return image

"""Verify traffic models on evenly sampled frames from a local video."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import model_path, preferred_device
from yoloe_backend import YoloEBackend


TRAFFIC_CLASSES = ["person", "car", "bicycle", "motorcycle", "bus", "truck"]


def write_jpeg(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    encoded.tofile(str(path))


def sample_video(video_path: Path, count: int) -> tuple[list[tuple[int, np.ndarray]], dict[str, Any]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_count <= 0:
        capture.release()
        raise RuntimeError("Video reports no frames")

    indices = np.linspace(frame_count * 0.1, frame_count * 0.9, count, dtype=int)
    frames: list[tuple[int, np.ndarray]] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            raise RuntimeError(f"Could not read frame {index}")
        frames.append((int(index), frame))
    capture.release()

    metadata = {
        "path": str(video_path.resolve()),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "sample_indices": [index for index, _ in frames],
    }
    return frames, metadata


def box_records(result: Any) -> list[dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []
    records = []
    for class_id, confidence, xyxy in zip(
        boxes.cls.int().cpu().tolist(),
        boxes.conf.cpu().tolist(),
        boxes.xyxy.cpu().tolist(),
    ):
        records.append(
            {
                "class_id": class_id,
                "name": result.names.get(class_id, str(class_id)),
                "confidence": round(float(confidence), 4),
                "box": [round(float(value), 1) for value in xyxy],
            }
        )
    return records


def run_yolo(
    label: str,
    weight_path: str,
    frames: list[tuple[int, np.ndarray]],
    output_dir: Path,
    device: str,
    confidence: float,
) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(weight_path)
    model.to(device)
    frame_results = []
    for frame_index, frame in frames:
        started = time.perf_counter()
        result = model.predict(frame, device=device, imgsz=640, conf=confidence, verbose=False)[0]
        elapsed_ms = (time.perf_counter() - started) * 1000
        detections = box_records(result)
        output_path = output_dir / f"{label}_{frame_index:06d}.jpg"
        write_jpeg(output_path, result.plot())
        frame_results.append(
            {
                "frame": frame_index,
                "elapsed_ms": round(elapsed_ms, 1),
                "detections": detections,
                "output": str(output_path.resolve()),
            }
        )
        print(f"[{label}] frame={frame_index} detections={len(detections)} time={elapsed_ms:.1f} ms")

    names = getattr(model, "names", {})
    del model
    torch.cuda.empty_cache()
    return {"weights": weight_path, "classes": names, "frames": frame_results}


def draw_yoloe(frame: np.ndarray, result: dict[str, Any]) -> np.ndarray:
    image = frame.copy()
    overlay = image.copy()
    for mask in result["masks"]:
        overlay[mask.astype(bool)] = (50, 180, 255)
    image = cv2.addWeighted(overlay, 0.3, image, 0.7, 0)

    for box, name, track_id in zip(result["boxes"], result["names"], result["ids"]):
        if box is None:
            continue
        x1, y1, x2, y2 = (int(value) for value in box)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 255), 3)
        suffix = f" #{track_id}" if track_id is not None else ""
        cv2.putText(
            image,
            f"{name}{suffix}",
            (x1, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
    return image


def run_yoloe(
    frames: list[tuple[int, np.ndarray]],
    output_dir: Path,
    device: str,
    confidence: float,
) -> dict[str, Any]:
    backend = YoloEBackend(device=device)
    backend.set_text_classes(TRAFFIC_CLASSES)
    frame_results = []
    for frame_index, frame in frames:
        started = time.perf_counter()
        result = backend.segment(frame, conf=confidence, imgsz=640, persist=True)
        elapsed_ms = (time.perf_counter() - started) * 1000
        detections = []
        for box, name, track_id in zip(result["boxes"], result["names"], result["ids"]):
            detections.append(
                {
                    "name": name,
                    "track_id": track_id,
                    "box": None if box is None else [round(float(value), 1) for value in box],
                }
            )
        output_path = output_dir / f"yoloe_traffic_{frame_index:06d}.jpg"
        write_jpeg(output_path, draw_yoloe(frame, result))
        frame_results.append(
            {
                "frame": frame_index,
                "elapsed_ms": round(elapsed_ms, 1),
                "detections": detections,
                "output": str(output_path.resolve()),
            }
        )
        print(f"[yoloe_traffic] frame={frame_index} detections={len(detections)} time={elapsed_ms:.1f} ms")

    del backend
    torch.cuda.empty_cache()
    return {"weights": model_path("YOLOE_MODEL_PATH", "yoloe-11l-seg.pt"), "classes": TRAFFIC_CLASSES, "frames": frame_results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/traffic_model_verification"))
    parser.add_argument("--device", default=preferred_device())
    parser.add_argument("--conf", type=float, default=0.2)
    args = parser.parse_args()

    if args.samples < 1:
        parser.error("--samples must be at least 1")
    video_path = args.video.expanduser()
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path
    if not video_path.exists():
        parser.error(f"video not found: {video_path}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frames, video_metadata = sample_video(video_path, args.samples)
    summary: dict[str, Any] = {
        "device": args.device,
        "video": video_metadata,
        "models": {},
    }
    summary["models"]["blindpath"] = run_yolo(
        "blindpath",
        model_path("BLIND_PATH_MODEL", "yolo-seg.pt"),
        frames,
        args.output_dir,
        args.device,
        args.conf,
    )
    summary["models"]["trafficlight"] = run_yolo(
        "trafficlight",
        model_path("TRAFFIC_LIGHT_MODEL", "trafficlight.pt"),
        frames,
        args.output_dir,
        args.device,
        args.conf,
    )
    summary["models"]["yoloe_traffic"] = run_yoloe(
        frames,
        args.output_dir,
        args.device,
        args.conf,
    )

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary: {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

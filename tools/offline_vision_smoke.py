# -*- coding: utf-8 -*-
"""Run one offline vision smoke test on a still image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import model_path, preferred_device


def load_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return img


def run_yolo(image: np.ndarray, model_env: str, filename: str, output: Path) -> None:
    from ultralytics import YOLO

    model = YOLO(model_path(model_env, filename))
    device = preferred_device()
    results = model.predict(image, device=device, verbose=False)
    vis = results[0].plot() if results else image
    cv2.imwrite(str(output), vis)
    names = getattr(model, "names", None)
    print(f"YOLO smoke OK on {device}; names={names}; output={output}")


def run_traffic(image: np.ndarray, output: Path) -> None:
    import trafficlight_detection

    result = trafficlight_detection.process_single_frame(image)
    cv2.imwrite(str(output), result["vis_image"])
    print(f"traffic detected={result['detected_light']} stable={result['stable_light']} output={output}")


def run_hand(image: np.ndarray, output: Path) -> None:
    import mediapipe as mp
    from mediapipe.framework.formats import landmark_pb2
    from mediapipe_utils import base_options_from_path

    task_path = model_path("HAND_TASK_PATH", "hand_landmarker.task")
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=base_options_from_path(task_path),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=2,
    )
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)

    vis = image.copy()
    for hand in result.hand_landmarks:
        proto = landmark_pb2.NormalizedLandmarkList()
        proto.landmark.extend(
            landmark_pb2.NormalizedLandmark(x=p.x, y=p.y, z=p.z) for p in hand
        )
        mp.solutions.drawing_utils.draw_landmarks(vis, proto, mp.solutions.hands.HAND_CONNECTIONS)
    cv2.imwrite(str(output), vis)
    print(f"hands={len(result.hand_landmarks)} output={output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--mode", choices=["blindpath", "shopping", "traffic", "hand"], default="blindpath")
    parser.add_argument("--output", type=Path, default=Path("offline_vision_output.jpg"))
    args = parser.parse_args()

    image = load_image(args.image)
    if args.mode == "blindpath":
        run_yolo(image, "BLIND_PATH_MODEL", "yolo-seg.pt", args.output)
    elif args.mode == "shopping":
        run_yolo(image, "SHOPPING_MODEL", "shoppingbest5.pt", args.output)
    elif args.mode == "traffic":
        run_traffic(image, args.output)
    else:
        run_hand(image, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Verify model file presence, with an optional lightweight load test."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import model_path, preferred_device


MODEL_SPECS = [
    ("blind path segmentation", "BLIND_PATH_MODEL", "yolo-seg.pt", "yolo"),
    ("YOLOE obstacle/open vocabulary", "YOLOE_MODEL_PATH", "yoloe-11l-seg.pt", "yoloe"),
    ("traffic light", "TRAFFIC_LIGHT_MODEL", "trafficlight.pt", "yolo"),
    ("shopping fallback", "SHOPPING_MODEL", "shoppingbest5.pt", "yolo"),
    ("MediaPipe hand landmarker", "HAND_TASK_PATH", "hand_landmarker.task", "mediapipe"),
]


def load_yolo(path: Path, kind: str) -> tuple[bool, str]:
    try:
        if kind == "yoloe":
            try:
                from ultralytics import YOLOE as Model
            except Exception:
                from ultralytics import YOLO as Model
        else:
            from ultralytics import YOLO as Model

        model = Model(str(path))
        device = preferred_device()
        model.to(device)
        names = getattr(model, "names", None)
        return True, f"loaded on {device}; names={names}"
    except Exception as exc:
        return False, str(exc)


def load_mediapipe(path: Path) -> tuple[bool, str]:
    try:
        import mediapipe as mp
        from mediapipe_utils import base_options_from_path

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options_from_path(path),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_hands=1,
        )
        landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        landmarker.close()
        return True, "loaded"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true", help="Actually load each model; slower and requires dependencies.")
    args = parser.parse_args()

    failures = 0
    for label, env_name, filename, kind in MODEL_SPECS:
        path = Path(model_path(env_name, filename))
        if not path.exists():
            print(f"[MISSING] {label}: {path}")
            failures += 1
            continue
        print(f"[FOUND]   {label}: {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")

        if args.load:
            ok, detail = load_mediapipe(path) if kind == "mediapipe" else load_yolo(path, kind)
            print(f"          {'OK' if ok else 'FAIL'} {detail}")
            if not ok:
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

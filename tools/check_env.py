# -*- coding: utf-8 -*-
"""Check the local runtime before starting the AI glasses server."""

from __future__ import annotations

import importlib.util
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import dashscope_api_key, model_path, preferred_device


MODULES = [
    "fastapi",
    "uvicorn",
    "websockets",
    "cv2",
    "numpy",
    "ultralytics",
    "clip",
    "lap",
    "torch",
    "torchaudio",
    "mediapipe",
    "dashscope",
    "openai",
    "funasr",
    "requests",
    "pyaudio",
    "pygame",
    "pyttsx3",
]

MODELS = {
    "BLIND_PATH_MODEL": "yolo-seg.pt",
    "OBSTACLE_MODEL": "yoloe-11l-seg.pt",
    "YOLOE_MODEL_PATH": "yoloe-11l-seg.pt",
    "TRAFFIC_LIGHT_MODEL": "trafficlight.pt",
    "SHOPPING_MODEL": "shoppingbest5.pt",
    "HAND_TASK_PATH": "hand_landmarker.task",
}

AUXILIARY_ASSETS = {
    "YOLOE_TEXT_ENCODER": ROOT / "mobileclip_blt.ts",
}


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    print("== Python ==")
    print(f"Executable: {sys.executable}")
    print(f"Version:    {sys.version.split()[0]}")
    print(f"Platform:   {platform.platform()}")
    print(f"Project:    {ROOT}")
    print()

    print("== Python modules ==")
    missing = []
    for name in MODULES:
        ok = has_module(name)
        print(f"{name:14} {'OK' if ok else 'MISSING'}")
        if not ok:
            missing.append(name)
    print()

    print("== Torch device ==")
    if has_module("torch"):
        import torch

        print(f"torch:      {torch.__version__}")
        print(f"cuda:       {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"gpu:        {torch.cuda.get_device_name(0)}")
    print(f"preferred:  {preferred_device()}")
    print()

    print("== DashScope ==")
    print("configured: YES" if dashscope_api_key(required=False) else "configured: NO")
    print()

    print("== Model files ==")
    missing_models = []
    for env_name, filename in MODELS.items():
        path = Path(model_path(env_name, filename))
        ok = path.exists()
        print(f"{env_name:20} {'OK' if ok else 'MISSING'} {path}")
        if not ok:
            missing_models.append(env_name)
    for asset_name, path in AUXILIARY_ASSETS.items():
        ok = path.exists()
        print(f"{asset_name:20} {'OK' if ok else 'MISSING'} {path}")
        if not ok:
            missing_models.append(asset_name)

    if missing or missing_models:
        print()
        print("Result: NOT READY")
        if missing:
            print("Missing modules:", ", ".join(missing))
        if missing_models:
            print("Missing models:", ", ".join(missing_models))
        return 1

    print()
    print("Result: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Shared runtime configuration for the reproduction-friendly setup."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"

PLACEHOLDER_VALUES = {
    "",
    "your_api_key_here",
    "sk-xxxxx",
    "change_me",
    "changeme",
    "replace_me",
}


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def configured(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in PLACEHOLDER_VALUES


def dashscope_api_key(required: bool = False) -> Optional[str]:
    key = env("DASHSCOPE_API_KEY")
    if configured(key):
        return key
    if required:
        raise RuntimeError(
            "DASHSCOPE_API_KEY is not configured. Copy .env.example to .env "
            "and fill in a real DashScope key before using ASR/Qwen features."
        )
    return None


def dashscope_base_url() -> str:
    return env("DASHSCOPE_COMPAT_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return BASE_DIR / path


def path_from_env(name: str, default_relative: str) -> str:
    raw = env(name, default_relative)
    return str(project_path(raw))


def model_path(name: str, filename: str) -> str:
    return path_from_env(name, str(Path("model") / filename))


def preferred_device(default: str = "cuda:0") -> str:
    device = env("AIGLASS_DEVICE", default)
    if device.startswith("cuda"):
        try:
            import torch

            if not torch.cuda.is_available():
                return "cpu"
        except Exception:
            return "cpu"
    return device

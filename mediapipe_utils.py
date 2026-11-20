"""MediaPipe model loading helpers for Windows-compatible paths."""

from pathlib import Path
from typing import Union

import mediapipe as mp


def base_options_from_path(path: Union[str, Path]) -> mp.tasks.BaseOptions:
    """Load a task model from bytes so non-ASCII Windows paths work."""
    model_bytes = Path(path).read_bytes()
    return mp.tasks.BaseOptions(model_asset_buffer=model_bytes)

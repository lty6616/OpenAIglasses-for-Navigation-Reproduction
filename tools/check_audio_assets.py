# -*- coding: utf-8 -*-
"""Check local prerecorded voice/audio assets without starting the server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import path_from_env


def iter_asset_files(value: object) -> list[str]:
    """Return referenced audio file names from supported map formats."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        files = value.get("files")
        if isinstance(files, list):
            return [item for item in files if isinstance(item, str)]
        if isinstance(files, str):
            return [files]
        for key in ("file", "path", "filename", "name"):
            item = value.get(key)
            if isinstance(item, str):
                return [item]
    return []


def main() -> int:
    voice_dir = Path(path_from_env("VOICE_DIR", "voice"))
    music_dir = Path(path_from_env("MUSIC_DIR", "music"))
    map_file = voice_dir / "map.zh-CN.json"

    print(f"voice_dir: {voice_dir}")
    print(f"music_dir: {music_dir}")

    failures = 0
    if not map_file.exists():
        print(f"[MISSING] {map_file}")
        failures += 1
    else:
        data = json.loads(map_file.read_text(encoding="utf-8"))
        missing = []
        malformed = []
        for text, entry in data.items():
            files = iter_asset_files(entry)
            if not files:
                malformed.append(text)
                missing.append((text, "<empty>"))
                continue
            path = voice_dir / files[0]
            if not path.exists():
                missing.append((text, files[0]))
        print(f"voice mappings: {len(data)}")
        print(f"malformed maps: {len(malformed)}")
        print(f"missing files:  {len(missing)}")
        for text, file_name in missing[:20]:
            print(f"  - {text}: {file_name}")
        failures += len(missing)

    music_count = len(list(music_dir.glob("*.wav"))) + len(list(music_dir.glob("*.WAV")))
    print(f"music wav files: {music_count}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

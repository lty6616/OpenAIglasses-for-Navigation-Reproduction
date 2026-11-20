# -*- coding: utf-8 -*-
"""Smoke-test Qwen-Omni with one local image plus a text prompt."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import dashscope_api_key, dashscope_base_url


def image_to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    if len(encoded.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("Base64 image is larger than 10 MB; resize/compress it before calling Qwen-Omni.")
    return f"data:{mime};base64,{encoded}"


def get_audio_delta(delta: Any) -> str:
    audio = getattr(delta, "audio", None)
    if isinstance(audio, dict):
        data = audio.get("data")
        return data if isinstance(data, str) else ""
    data = getattr(audio, "data", "") if audio is not None else ""
    return data if isinstance(data, str) else ""


def write_pcm16_wav(path: Path, pcm_chunks: list[bytes], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for chunk in pcm_chunks:
            wav.writeframes(chunk)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send one image plus text to Qwen-Omni.")
    parser.add_argument("image", help="Path to a local image.")
    parser.add_argument(
        "--prompt",
        default=os.getenv("QWEN_OMNI_TEST_PROMPT", "请用中文简要描述这张图片，并说明是否有明显障碍物。"),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("QWEN_OMNI_TEST_MODEL", os.getenv("QWEN_OMNI_MODEL", "qwen3.5-omni-plus")),
    )
    parser.add_argument("--base-url", default=dashscope_base_url())
    parser.add_argument("--with-audio", action="store_true", help="Request text plus audio output.")
    parser.add_argument("--voice", default=os.getenv("QWEN_OMNI_VOICE", "Cherry"))
    parser.add_argument("--audio-rate", type=int, default=int(os.getenv("QWEN_OMNI_AUDIO_RATE", "24000")))
    parser.add_argument(
        "--audio-output",
        default=os.getenv("QWEN_OMNI_AUDIO_OUTPUT", str(ROOT / "outputs" / "qwen_omni_reply.wav")),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    image_path = Path(args.image).expanduser()
    if not image_path.is_absolute():
        image_path = Path.cwd() / image_path
    if not image_path.exists():
        print(f"[ERROR] Image file not found: {image_path}", file=sys.stderr)
        return 2

    try:
        from openai import OpenAI
    except ImportError as exc:
        print("[ERROR] Missing OpenAI SDK. Install it with: pip install 'openai>=1.52.0'", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        image_url = image_to_data_url(image_path)
        client = OpenAI(api_key=dashscope_api_key(required=True), base_url=args.base_url)

        request: dict[str, Any] = {
            "model": args.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": args.prompt},
                    ],
                }
            ],
            "modalities": ["text", "audio"] if args.with_audio else ["text"],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if args.with_audio:
            request["audio"] = {"voice": args.voice, "format": "pcm16"}

        print(f"[OMNI] model={args.model}")
        print(f"[OMNI] image={image_path}")
        print("[OMNI TEXT]")

        audio_chunks: list[bytes] = []
        usage = None
        completion = client.chat.completions.create(**request)
        for chunk in completion:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
                continue
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                print(text, end="", flush=True)
            audio_b64 = get_audio_delta(delta)
            if audio_b64:
                audio_chunks.append(base64.b64decode(audio_b64))
        print()

        if args.with_audio and audio_chunks:
            output = Path(args.audio_output).expanduser()
            if not output.is_absolute():
                output = Path.cwd() / output
            write_pcm16_wav(output, audio_chunks, args.audio_rate)
            print(f"[OMNI AUDIO] {output}")
        if usage:
            print(f"[OMNI USAGE] {usage}")
    except Exception as exc:
        print(f"[ERROR] Qwen-Omni test failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

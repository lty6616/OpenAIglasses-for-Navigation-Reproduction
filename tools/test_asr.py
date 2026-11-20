# -*- coding: utf-8 -*-
"""Smoke-test Paraformer ASR with a local FunASR model or local API server."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import preferred_device


def normalize_funasr_device(device: str) -> str:
    if device.startswith("cuda"):
        return "cuda"
    return "cpu"


def extract_text(result: Any) -> str:
    items = result if isinstance(result, list) else [result]
    texts: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("text") or item.get("sentence") or item.get("result")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        elif isinstance(item, str) and item.strip():
            texts.append(item.strip())
    return "\n".join(texts)


def run_local(args: argparse.Namespace, wav_path: Path) -> Any:
    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise RuntimeError(
            "Missing FunASR. Install local ASR dependencies first: "
            "pip install torch torchaudio funasr"
        ) from exc

    model_kwargs: dict[str, Any] = {
        "model": args.model,
        "device": normalize_funasr_device(args.device),
    }
    if not args.no_vad:
        model_kwargs["vad_model"] = args.vad_model
    if not args.no_punc:
        model_kwargs["punc_model"] = args.punc_model

    print(f"[ASR] Loading local FunASR model: {model_kwargs}")
    model = AutoModel(**model_kwargs)

    generate_kwargs: dict[str, Any] = {
        "input": str(wav_path),
        "batch_size_s": args.batch_size_s,
    }
    if args.hotword:
        generate_kwargs["hotword"] = args.hotword

    print(f"[ASR] Recognizing: {wav_path}")
    return model.generate(**generate_kwargs)


def run_server(args: argparse.Namespace, wav_path: Path) -> Any:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Missing requests. Install it with: pip install requests") from exc

    data = {
        "model": args.model,
        "response_format": args.response_format,
    }
    with wav_path.open("rb") as fh:
        files = {"file": (wav_path.name, fh, "audio/wav")}
        print(f"[ASR] POST {args.server_url}")
        response = requests.post(args.server_url, data=data, files=files, timeout=args.timeout)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return response.text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recognize one WAV file with Paraformer/FunASR.",
    )
    parser.add_argument("wav", help="Path to a 16 kHz WAV recording.")
    parser.add_argument(
        "--mode",
        choices=["local", "server"],
        default=os.getenv("PARAFORMER_MODE", "local"),
        help="local loads FunASR in this process; server calls a local funasr-server endpoint.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("PARAFORMER_MODEL", "paraformer-zh"),
        help="FunASR model name. Use paraformer-zh for local Chinese ASR.",
    )
    parser.add_argument("--device", default=preferred_device(), help="cuda:0/cuda/cpu; local mode normalizes cuda:* to cuda.")
    parser.add_argument("--vad-model", default=os.getenv("PARAFORMER_VAD_MODEL", "fsmn-vad"))
    parser.add_argument("--punc-model", default=os.getenv("PARAFORMER_PUNC_MODEL", "ct-punc"))
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD helper model in local mode.")
    parser.add_argument("--no-punc", action="store_true", help="Disable punctuation helper model in local mode.")
    parser.add_argument("--hotword", default=os.getenv("PARAFORMER_HOTWORD", ""))
    parser.add_argument("--batch-size-s", type=int, default=int(os.getenv("PARAFORMER_BATCH_SIZE_S", "60")))
    parser.add_argument(
        "--server-url",
        default=os.getenv("PARAFORMER_SERVER_URL", "http://127.0.0.1:8000/v1/audio/transcriptions"),
    )
    parser.add_argument("--response-format", default=os.getenv("PARAFORMER_RESPONSE_FORMAT", "verbose_json"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("PARAFORMER_TIMEOUT_SEC", "120")))
    parser.add_argument("--json", action="store_true", help="Print the full raw result as JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    wav_path = Path(args.wav).expanduser()
    if not wav_path.is_absolute():
        wav_path = Path.cwd() / wav_path
    if not wav_path.exists():
        print(f"[ERROR] WAV file not found: {wav_path}", file=sys.stderr)
        return 2
    if wav_path.suffix.lower() != ".wav":
        print(f"[WARN] Expected .wav input, got: {wav_path.suffix}", file=sys.stderr)

    try:
        result = run_local(args, wav_path) if args.mode == "local" else run_server(args, wav_path)
    except Exception as exc:
        print(f"[ERROR] ASR test failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        text = extract_text(result)
        print("\n[ASR TEXT]")
        print(text or json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

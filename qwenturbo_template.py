# -*- coding: utf-8 -*-
"""Small Qwen text-chat smoke test using the shared project config."""

from __future__ import annotations

import os

from openai import OpenAI

from config import dashscope_api_key, dashscope_base_url


def main() -> int:
    client = OpenAI(
        api_key=dashscope_api_key(required=True),
        base_url=dashscope_base_url(),
    )

    messages = [
        {
            "role": "user",
            "content": "Briefly introduce yourself as the navigation-glasses assistant.",
        }
    ]
    completion = client.chat.completions.create(
        model=os.getenv("QWEN_TEXT_MODEL", "qwen-turbo"),
        messages=messages,
        extra_body={"enable_thinking": True},
        stream=True,
    )

    is_answering = False
    print("\n" + "=" * 20 + " reasoning " + "=" * 20)
    for chunk in completion:
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning is not None and not is_answering:
            print(reasoning, end="", flush=True)

        content = getattr(delta, "content", None)
        if content:
            if not is_answering:
                print("\n" + "=" * 20 + " answer " + "=" * 20)
                is_answering = True
            print(content, end="", flush=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Small terminal chat client for a local Ollama model."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


MODEL = os.environ.get("ATHENA_MODEL", "qwen2.5:1.5b")
OLLAMA_URL = os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
SYSTEM_PROMPT = os.environ.get(
    "ATHENA_SYSTEM_PROMPT",
    "You are ATHENA, a concise local AI assistant for engineering, learning, and personal productivity.",
)


def ask_ollama(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": 2048,
            "temperature": 0.4,
        },
    }

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Open Ollama, then run `ollama pull qwen2.5:1.5b`."
        ) from exc

    message = data.get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {data}")

    return content.strip()


def main() -> int:
    print(f"ATHENA local chat - model: {MODEL}")
    print("Type /exit to quit.")
    print()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_text:
            continue
        if user_text in {"/exit", "/quit"}:
            return 0

        messages.append({"role": "user", "content": user_text})

        try:
            answer = ask_ollama(messages)
        except RuntimeError as exc:
            print(f"error> {exc}")
            return 1

        messages.append({"role": "assistant", "content": answer})
        print(f"athena> {answer}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())

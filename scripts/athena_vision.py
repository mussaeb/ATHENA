#!/usr/bin/env python3
"""Describe a local image with an explicitly chosen Ollama vision model."""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from athena_common import load_dotenv


load_dotenv()

OLLAMA_URL = os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
VISION_MODEL = os.environ.get("ATHENA_VISION_MODEL", "").strip()
NUM_CTX = int(os.environ.get("ATHENA_NUM_CTX", "1536"))
MAX_IMAGE_BYTES = 4 * 1024 * 1024
ALLOWED_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
DISABLED_MESSAGE = (
    "Vision is not enabled. The default chat model is text-only. "
    "Set ATHENA_VISION_MODEL to a local vision model, such as moondream, only when this machine has enough memory. "
    "An 8 GB Mac should keep the normal chat model small and leave vision off until you choose to try it."
)


def validate_image(path: Path) -> None:
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Vision accepts png, jpg, jpeg, gif, and webp files.")
    if not path.is_file():
        raise ValueError(f"Image not found: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError("The image file is empty.")
    if size > MAX_IMAGE_BYTES:
        raise ValueError("The image is larger than 4 MB. Use a smaller image on this machine.")


def build_payload(model: str, question: str, image_bytes: bytes) -> dict:
    return {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": question,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            }
        ],
        "options": {"num_ctx": NUM_CTX, "temperature": 0.2},
    }


def describe_image(path: Path, question: str, model: str = VISION_MODEL) -> str:
    if not model:
        return DISABLED_MESSAGE

    validate_image(path)
    payload = build_payload(model, question, path.read_bytes())
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
        raise RuntimeError("Could not reach Ollama. Open Ollama and check ATHENA_VISION_MODEL.") from exc
    except TimeoutError as exc:
        raise RuntimeError("Ollama took too long to describe the image.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned a response that was not JSON.") from exc

    content = data.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {data}")
    return content.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Describe one local image with Ollama.")
    parser.add_argument("image", type=Path)
    parser.add_argument("question", nargs="*")
    args = parser.parse_args()
    question = " ".join(args.question).strip() or "Describe this image."

    try:
        print(describe_image(args.image, question))
    except (RuntimeError, ValueError, OSError) as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

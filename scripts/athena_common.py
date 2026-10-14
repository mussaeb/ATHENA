#!/usr/bin/env python3
"""Shared helpers for the dependency-free ATHENA scripts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(root: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env without overriding existing variables."""

    env_path = (root or PROJECT_ROOT) / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())}


def clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n...[truncated at {limit} characters]"


def redact_secrets(text: str) -> str:
    return re.sub(r"//[^/\s:@]+:[^/\s@]+@", "//", text)


def append_safety_log(action: str, detail: str, approved: bool, root: Path | None = None) -> None:
    log_dir = (root or PROJECT_ROOT) / "logs" / "safety"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "approved": approved,
        "detail": clip(detail, 2000),
    }
    with (log_dir / "safety.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

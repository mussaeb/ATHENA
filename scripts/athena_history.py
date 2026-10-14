#!/usr/bin/env python3
"""Search saved ATHENA chat transcripts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from athena_common import PROJECT_ROOT, clip, tokenize


LOG_DIR = PROJECT_ROOT / "logs" / "chats"


def slugify(name: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in name.strip())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:40] or "chat"


def transcript_filename(stamp: str, session_name: str) -> str:
    return f"athena-{stamp}-{slugify(session_name)}.jsonl"


def session_label(path: Path, entry: dict | None = None) -> str:
    if entry and entry.get("session"):
        return str(entry["session"])

    stem = path.stem
    if stem.startswith("athena-chat-"):
        return "chat"
    parts = stem.split("-")
    if len(parts) >= 4 and parts[0] == "athena" and parts[1].isdigit():
        return "-".join(parts[3:]) or "chat"
    return stem


def iter_entries(log_dir: Path):
    if not log_dir.exists():
        return

    files = sorted(log_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            entry["_file"] = path.name
            entry["_line"] = line_number
            yield entry


def list_sessions(log_dir: Path = LOG_DIR, limit: int = 15) -> str:
    if not log_dir.exists():
        return "No saved chats yet."

    files = sorted(log_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not files:
        return "No saved chats yet."

    lines = []
    for path in files[:limit]:
        first_user = ""
        label = session_label(path)
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue
                if entry.get("session"):
                    label = str(entry["session"])
                if entry.get("role") == "user" and not first_user:
                    first_user = " ".join(str(entry.get("content", "")).split())
        except (OSError, json.JSONDecodeError):
            first_user = ""
        snippet = clip(first_user, 80).replace("\n", " ") if first_user else "(no user message yet)"
        lines.append(f"- {path.name} [{label}] {snippet}")

    return "\n".join(lines)


def search_chats(query: str, log_dir: Path = LOG_DIR, limit: int = 5) -> str:
    query = query.strip()
    if not query:
        return "Tell me what to look for in past chats."

    query_tokens = tokenize(query)
    matches = []
    for entry in iter_entries(log_dir):
        if entry.get("role") == "system":
            continue
        content = str(entry.get("content", ""))
        haystack = content.lower()
        overlap = query_tokens & tokenize(content)
        if query_tokens and not overlap and query.lower() not in haystack:
            continue
        if not query_tokens and query.lower() not in haystack:
            continue
        score = len(overlap) / max(len(query_tokens), 1)
        if query.lower() in haystack:
            score += 0.25
        matches.append((score, entry))

    matches.sort(key=lambda item: (item[0], str(item[1].get("timestamp", ""))), reverse=True)
    chosen = matches[:limit]
    if not chosen:
        return "No matching saved chats found."

    lines = []
    for number, (score, entry) in enumerate(chosen, start=1):
        role = entry.get("role", "unknown")
        timestamp = entry.get("timestamp", "")
        lines.append(f"[{number}] {entry['_file']} {timestamp} role={role} score={score:.2f}")
        lines.append(clip(" ".join(str(entry.get("content", "")).split()), 500))
        lines.append("")
    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="List and search ATHENA chat transcripts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent chat transcripts.")
    list_parser.add_argument("--limit", type=int, default=15)
    list_parser.add_argument("--log-dir", type=Path, default=LOG_DIR)

    search_parser = subparsers.add_parser("search", help="Search saved chat transcripts.")
    search_parser.add_argument("query", nargs="+")
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--log-dir", type=Path, default=LOG_DIR)

    args = parser.parse_args()
    if args.command == "list":
        print(list_sessions(args.log_dir, limit=args.limit))
        return 0

    print(search_chats(" ".join(args.query), log_dir=args.log_dir, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

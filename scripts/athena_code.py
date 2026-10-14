#!/usr/bin/env python3
"""Read-only project inspection, tests, and reviewed file edits."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from athena_common import PROJECT_ROOT, append_safety_log, clip, tokenize


MAX_READ_CHARS = 12_000
PROPOSAL_DIR = PROJECT_ROOT / "logs" / "proposals"
SKIPPED_DIRS = {".git", ".idea", ".venv", "__pycache__", "logs", "models", "node_modules", "venv"}
BINARY_SUFFIXES = {".dll", ".exe", ".gif", ".jpeg", ".jpg", ".pdf", ".png", ".pyc", ".webp", ".zip"}
ALLOWED_TOP_LEVEL = {"config", "docs", "infrastructure", "memory", "rag", "scripts", "tests", "vision", "voice"}


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def resolve_inside(root: Path, user_path: str) -> Path:
    candidate = Path(user_path)
    root_resolved = root.resolve()
    resolved = candidate.resolve() if candidate.is_absolute() else (root_resolved / candidate).resolve()
    resolved.relative_to(root_resolved)
    return resolved


def is_secret(relative: Path) -> bool:
    name = relative.name.lower()
    if name in {".env", "credentials.json", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa", "private.md"}:
        return True
    if name.endswith((".kdbx", ".key", ".p12", ".pem", ".pfx")):
        return True
    return ".git" in relative.parts or ".ssh" in relative.parts


def is_writable(relative: Path) -> bool:
    if is_secret(relative) or not relative.parts:
        return False
    if relative.name == ".env":
        return False
    if len(relative.parts) == 1 and relative.name == "README.md":
        return True
    if relative.parts[0] not in ALLOWED_TOP_LEVEL:
        return False
    if relative.parts[0] == "rag" and (len(relative.parts) < 2 or relative.parts[1] != "sources"):
        return False
    return True


def read_project_file(root: Path, user_path: str) -> str:
    target = resolve_inside(root, user_path)
    relative = target.relative_to(root.resolve())
    if is_secret(relative):
        raise ValueError(f"Refusing to read {relative.as_posix()}.")
    if not target.is_file():
        raise ValueError(f"File not found: {relative.as_posix()}")
    if target.suffix.lower() in BINARY_SUFFIXES:
        raise ValueError("This is a binary file. Use /see for images.")
    if target.stat().st_size > 1_000_000:
        raise ValueError("File is too large to read here.")

    text = target.read_text(encoding="utf-8", errors="replace")
    return clip(text, MAX_READ_CHARS)


def list_project_files(root: Path, query: str = "", limit: int = 200) -> str:
    query_tokens = tokenize(query)
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_DIRS and not name.startswith(".")]
        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                relative = path.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            if is_secret(relative):
                continue
            if query_tokens and not (query_tokens & tokenize(relative.as_posix())):
                continue
            matches.append(relative.as_posix())
            if len(matches) >= limit:
                lines = [f"- {item}" for item in sorted(matches)]
                lines.append(f"... stopped at {limit} files")
                return "\n".join(lines)
    if not matches:
        return "No matching project files found."
    return "\n".join(f"- {item}" for item in sorted(matches))


def run_git(root: Path, args: list[str]) -> str:
    if shutil.which("git") is None:
        return "Git is not installed or not on PATH."

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Git failed: {exc}"

    output = result.stdout.strip()
    if result.returncode != 0:
        return result.stderr.strip() or output or f"git exited {result.returncode}"
    return output or "(no output)"


def git_status(root: Path = PROJECT_ROOT) -> str:
    return run_git(root, ["status", "--short", "--branch"])


def git_diff(root: Path = PROJECT_ROOT) -> str:
    return run_git(root, ["diff", "--stat"])


def git_log(root: Path = PROJECT_ROOT) -> str:
    return run_git(root, ["log", "-8", "--oneline"])


def test_command(root: Path = PROJECT_ROOT) -> list[str]:
    return [sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"]


def run_tests(root: Path = PROJECT_ROOT) -> tuple[int, str]:
    if not (root / "tests").exists():
        return 1, "No tests directory found."

    try:
        result = subprocess.run(
            test_command(root),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"Tests failed to start: {exc}"

    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}".strip()
    return result.returncode, output or "(no output)"


def parse_replacement(model_text: str) -> tuple[str, str]:
    end = model_text.rfind("<<<END>>>")
    middle = model_text.rfind("<<<WITH>>>", 0, end if end != -1 else 0)
    start = model_text.rfind("<<<REPLACE>>>", 0, middle if middle != -1 else 0)
    if start == -1 or middle == -1 or end == -1 or not (start < middle < end):
        raise ValueError("The draft did not include <<<REPLACE>>>, <<<WITH>>>, and <<<END>>>. No file was changed.")

    old = unwrap_block(model_text[start + len("<<<REPLACE>>>") : middle])
    new = unwrap_block(model_text[middle + len("<<<WITH>>>") : end])
    return old, new


def parse_new_file(model_text: str) -> str:
    end = model_text.rfind("<<<END>>>")
    start = model_text.rfind("<<<ATHENA_FILE>>>", 0, end if end != -1 else 0)
    if start == -1 or end == -1 or end < start:
        raise ValueError("The draft did not include <<<ATHENA_FILE>>> and <<<END>>>. No file was created.")
    content = unwrap_block(model_text[start + len("<<<ATHENA_FILE>>>") : end])
    if not content.strip():
        raise ValueError("The draft file is empty. No file was created.")
    if not content.endswith("\n"):
        content += "\n"
    return content


def unwrap_block(text: str) -> str:
    if text.startswith("\r\n"):
        text = text[2:]
    elif text.startswith("\n"):
        text = text[1:]
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return text


def build_updated_text(original: str, old: str, new: str) -> str:
    original = normalize_newlines(original)
    old = normalize_newlines(old)
    new = normalize_newlines(new)
    if old == "":
        raise ValueError("The snippet to replace is empty. No file was changed.")

    count = original.count(old)
    if count == 0:
        raise ValueError("That snippet was not found in the file. No file was changed.")
    if count > 1:
        raise ValueError(f"That snippet appears {count} times. No file was changed.")
    return original.replace(old, new, 1)


def proposal_diff(relative: str, original: str, updated: str) -> str:
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )
    return diff or "No changes."


def save_proposal(proposal: dict, proposal_dir: Path = PROPOSAL_DIR) -> Path:
    proposal_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = json.dumps(proposal, indent=2, ensure_ascii=True)
    (proposal_dir / f"proposal-{stamp}.json").write_text(payload, encoding="utf-8")
    latest = proposal_dir / "latest.json"
    latest.write_text(payload, encoding="utf-8")
    return latest


def load_latest_proposal(proposal_dir: Path = PROPOSAL_DIR) -> dict:
    latest = proposal_dir / "latest.json"
    if not latest.is_file():
        raise ValueError("There is no proposal to apply. Use /propose first.")
    return json.loads(latest.read_text(encoding="utf-8"))


def apply_proposal(root: Path, proposal: dict) -> str:
    relative_text = str(proposal.get("path", ""))
    target = resolve_inside(root, relative_text)
    relative = target.relative_to(root.resolve())
    if is_secret(relative) or not is_writable(relative):
        raise ValueError(f"Refusing to write {relative.as_posix()}.")

    original = normalize_newlines(str(proposal.get("original", "")))
    updated = normalize_newlines(str(proposal.get("updated", "")))
    if target.exists():
        current = normalize_newlines(target.read_text(encoding="utf-8", errors="replace"))
        if current != original:
            raise ValueError("The file changed after the proposal was created. Make a new proposal.")
    elif original:
        raise ValueError("The original file is missing, so the proposal was not applied.")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    target.write_bytes(updated.encode("utf-8"))
    append_safety_log("apply", f"{relative.as_posix()}\n{proposal.get('diff', '')}", approved=True, root=root)
    return f"Applied proposal to {relative.as_posix()}."


def show_latest_proposal(proposal_dir: Path = PROPOSAL_DIR) -> str:
    proposal = load_latest_proposal(proposal_dir)
    diff = str(proposal.get("diff", ""))
    return f"Proposal for {proposal.get('path', 'unknown file')}\n\n{diff}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the ATHENA project and apply reviewed edits.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("git-status")
    subparsers.add_parser("git-diff")
    subparsers.add_parser("git-log")

    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("path")

    files_parser = subparsers.add_parser("files")
    files_parser.add_argument("query", nargs="*")

    subparsers.add_parser("test")
    subparsers.add_parser("show-proposal")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--yes", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "git-status":
            print(git_status())
        elif args.command == "git-diff":
            print(git_diff())
        elif args.command == "git-log":
            print(git_log())
        elif args.command == "read":
            print(read_project_file(PROJECT_ROOT, args.path))
        elif args.command == "files":
            print(list_project_files(PROJECT_ROOT, " ".join(args.query)))
        elif args.command == "test":
            code, output = run_tests()
            print(output)
            return code
        elif args.command == "show-proposal":
            print(show_latest_proposal())
        elif args.command == "apply":
            if not args.yes:
                print("Refusing to write. Review the diff, then run with --yes.")
                return 1
            print(apply_proposal(PROJECT_ROOT, load_latest_proposal()))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

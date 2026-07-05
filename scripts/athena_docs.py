#!/usr/bin/env python3
"""Lightweight local document indexing and search for ATHENA."""

from __future__ import annotations

import argparse
import os
import json
import re
import shutil
import subprocess
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "rag" / "sources"
INDEX_FILE = PROJECT_ROOT / "rag" / "index.json"
SOURCE_CONFIG_FILE = PROJECT_ROOT / "config" / "document_sources.json"
SOURCE_EXAMPLE_FILE = PROJECT_ROOT / "config" / "document_sources.example.json"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES = int(os.environ.get("ATHENA_DOCS_MAX_FILES", "250"))
MAX_DEPTH = int(os.environ.get("ATHENA_DOCS_MAX_DEPTH", "5"))
MAX_FIND_FILES = int(os.environ.get("ATHENA_DOCS_MAX_FIND_FILES", "5000"))
SUPPORTED_EXTENSIONS = {
    ".csv",
    ".docx",
    ".json",
    ".log",
    ".md",
    ".pdf",
    ".py",
    ".text",
    ".txt",
    ".tsv",
    ".xlsx",
    ".yaml",
    ".yml",
}
SKIPPED_DIR_NAMES = {
    ".Trash",
    ".cache",
    ".git",
    ".npm",
    ".ollama",
    ".ssh",
    ".venv",
    "Applications",
    "Library",
    "Movies",
    "Music",
    "node_modules",
    "venv",
}


def create_source_config(force: bool = False) -> bool:
    if SOURCE_CONFIG_FILE.exists() and not force:
        return False

    if SOURCE_EXAMPLE_FILE.exists():
        SOURCE_CONFIG_FILE.write_text(SOURCE_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        SOURCE_CONFIG_FILE.write_text(
            json.dumps({"sources": [SOURCE_DIR.as_posix()]}, indent=2),
            encoding="utf-8",
        )
    return True


def normalize_text(text: str) -> str:
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())}


def searchable_text(path: str, chunk: str) -> str:
    return f"{path}\n{chunk}"


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_docx(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as document:
            root = ElementTree.fromstring(document.read())

    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            parts.append(node.text)
        elif node.tag.endswith("}p"):
            parts.append("\n")

    return " ".join(parts)


def read_xlsx(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.iter():
                if item.tag.endswith("}t") and item.text:
                    shared_strings.append(item.text)

        for name in archive.namelist():
            if not name.startswith("xl/worksheets/") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for node in root.iter():
                if not node.tag.endswith("}v") or node.text is None:
                    continue
                value = node.text
                if value.isdigit():
                    index = int(value)
                    if 0 <= index < len(shared_strings):
                        value = shared_strings[index]
                parts.append(value)

    return "\n".join(parts)


def read_pdf(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("PDF support needs `pdftotext`. Install with `brew install poppler`.")

    result = subprocess.run(
        [pdftotext, str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pdftotext failed")

    return result.stdout


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".json", ".log", ".md", ".py", ".text", ".txt", ".tsv", ".yaml", ".yml"}:
        return read_text_file(path)
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".pdf":
        return read_pdf(path)

    raise RuntimeError(f"Unsupported file type: {suffix}")


def chunk_text(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - CHUNK_OVERLAP)

    return chunks


def expand_user_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def load_source_dirs() -> list[Path]:
    dirs = [SOURCE_DIR]
    if SOURCE_CONFIG_FILE.exists():
        config = json.loads(SOURCE_CONFIG_FILE.read_text(encoding="utf-8"))
        for raw_path in config.get("sources", []):
            path = expand_user_path(raw_path)
            if path.exists() and path.is_dir():
                dirs.append(path)

    seen = set()
    unique_dirs = []
    for path in dirs:
        key = path.as_posix()
        if key not in seen:
            unique_dirs.append(path)
            seen.add(key)
    return unique_dirs


def configured_source_paths() -> list[str]:
    if not SOURCE_CONFIG_FILE.exists():
        return []

    config = json.loads(SOURCE_CONFIG_FILE.read_text(encoding="utf-8"))
    return list(config.get("sources", []))


def should_skip_dir(path: Path) -> bool:
    return any(part in SKIPPED_DIR_NAMES for part in path.parts)


def display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def iter_source_files() -> list[Path]:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for source_dir in load_source_dirs():
        for dirpath, dirnames, filenames in os.walk(source_dir):
            dir_path = Path(dirpath)
            try:
                depth = len(dir_path.relative_to(source_dir).parts)
            except ValueError:
                depth = 0
            if depth >= MAX_DEPTH:
                dirnames[:] = []

            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in SKIPPED_DIR_NAMES and not dirname.startswith(".")
            ]
            if should_skip_dir(dir_path):
                continue
            for filename in filenames:
                path = dir_path / filename
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    file_size = path.stat().st_size
                except OSError:
                    continue
                if file_size > MAX_FILE_BYTES:
                    continue
                files.append(path)
                if len(files) >= MAX_FILES:
                    return sorted(set(files))

    return sorted(set(files))


def build_index() -> dict:
    documents = []
    errors = []

    for path in iter_source_files():
        relative_path = display_path(path)
        try:
            text = read_document(path)
            chunks = chunk_text(text)
        except Exception as exc:  # noqa: BLE001 - report per-file extraction failures.
            errors.append({"path": relative_path, "error": str(exc)})
            continue

        for chunk_number, chunk in enumerate(chunks, start=1):
            documents.append(
                {
                    "path": relative_path,
                    "chunk": chunk_number,
                    "text": chunk,
                    "tokens": sorted(tokenize(searchable_text(relative_path, chunk))),
                }
            )

    index = {
        "version": 1,
        "source_dirs": [display_path(path) for path in load_source_dirs()],
        "documents": documents,
        "errors": errors,
    }
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=True), encoding="utf-8")
    return index


def load_index() -> dict:
    if not INDEX_FILE.exists():
        return build_index()

    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def search_index(query: str, limit: int = 5) -> list[dict]:
    index = load_index()
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    results = []
    for item in index.get("documents", []):
        item_tokens = set(item.get("tokens", []))
        overlap = query_tokens & item_tokens
        if not overlap:
            continue
        score = len(overlap) / max(len(query_tokens), 1)
        results.append(
            {
                "score": score,
                "path": item["path"],
                "chunk": item["chunk"],
                "text": item["text"],
                "matched_terms": sorted(overlap),
            }
        )

    return sorted(results, key=lambda result: result["score"], reverse=True)[:limit]


def find_files(query: str, limit: int = 20) -> list[Path]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    matches = []
    scanned = 0
    for source_dir in load_source_dirs():
        for dirpath, dirnames, filenames in os.walk(source_dir):
            dir_path = Path(dirpath)
            try:
                depth = len(dir_path.relative_to(source_dir).parts)
            except ValueError:
                depth = 0
            if depth >= MAX_DEPTH:
                dirnames[:] = []

            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in SKIPPED_DIR_NAMES and not dirname.startswith(".")
            ]
            if should_skip_dir(dir_path):
                continue

            for filename in filenames:
                path = dir_path / filename
                scanned += 1
                if query_tokens & tokenize(display_path(path)):
                    matches.append(path)
                    if len(matches) >= limit:
                        return matches
                if scanned >= MAX_FIND_FILES:
                    return matches
    return matches


def format_results(results: list[dict]) -> str:
    if not results:
        return "No matching local documents found."

    lines = []
    for number, result in enumerate(results, start=1):
        lines.append(f"[{number}] {result['path']}#chunk-{result['chunk']} score={result['score']:.2f}")
        lines.append(result["text"])
        lines.append("")

    return "\n".join(lines).strip()


def format_file_results(results: list[Path]) -> str:
    if not results:
        return "No matching files found."

    return "\n".join(f"- {display_path(path)}" for path in results)


def print_sources() -> None:
    print(f"Default source: {display_path(SOURCE_DIR)}")
    print(f"Config file: {display_path(SOURCE_CONFIG_FILE)}")

    configured = configured_source_paths()
    if not configured:
        print("Configured folders: none yet")
        print("Run `python3 scripts/athena_docs.py init-sources` or use /initdocs in ATHENA chat.")
        return

    print("Configured folders:")
    for raw_path in configured:
        path = expand_user_path(raw_path)
        status = "ok" if path.exists() and path.is_dir() else "missing"
        print(f"- {raw_path} [{status}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Index and search ATHENA local documents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-sources", help="Create config/document_sources.json from the example.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite the existing local source config.")

    subparsers.add_parser("sources", help="Show configured document source folders.")

    subparsers.add_parser("index", help="Build the local document index.")

    search_parser = subparsers.add_parser("search", help="Search the local document index.")
    search_parser.add_argument("query", nargs="+")
    search_parser.add_argument("--limit", type=int, default=5)

    find_parser = subparsers.add_parser("findfile", help="Find source files by filename or path.")
    find_parser.add_argument("query", nargs="+")
    find_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.command == "init-sources":
        created = create_source_config(force=args.force)
        if created:
            print(f"Created {display_path(SOURCE_CONFIG_FILE)}")
        else:
            print(f"{display_path(SOURCE_CONFIG_FILE)} already exists")
        print("Edit it to choose which folders ATHENA may index.")
        return 0

    if args.command == "sources":
        print_sources()
        return 0

    if args.command == "index":
        index = build_index()
        print(f"Indexed {len(index['documents'])} chunks from {len(iter_source_files())} files.")
        print(f"Limits: max files={MAX_FILES}, max depth={MAX_DEPTH}, max file size={MAX_FILE_BYTES // (1024 * 1024)} MB")
        print("Sources:")
        for source_dir in index["source_dirs"]:
            print(f"- {source_dir}")
        if not SOURCE_CONFIG_FILE.exists():
            print("No extra source config found. Create config/document_sources.json to index folders like Documents or Desktop.")
        if index["errors"]:
            print("Some files could not be indexed:")
            for error in index["errors"]:
                print(f"- {error['path']}: {error['error']}")
        return 0

    if args.command == "search":
        results = search_index(" ".join(args.query), limit=args.limit)
        print(format_results(results))
        return 0

    if args.command == "findfile":
        results = find_files(" ".join(args.query), limit=args.limit)
        print(format_file_results(results))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

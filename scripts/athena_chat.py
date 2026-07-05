#!/usr/bin/env python3
"""Small terminal chat client for a local Ollama model."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
import urllib.error
import urllib.request


MODEL = os.environ.get("ATHENA_MODEL", "qwen2.5:1.5b")
OLLAMA_URL = os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
NUM_CTX = int(os.environ.get("ATHENA_NUM_CTX", "1536"))
DOCS_TIMEOUT = int(os.environ.get("ATHENA_DOCS_TIMEOUT", "300"))
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHAT_LOG_DIR = PROJECT_ROOT / "logs" / "chats"
MEMORY_FILE = PROJECT_ROOT / "memory" / "profile.md"
DOCS_SCRIPT = PROJECT_ROOT / "scripts" / "athena_docs.py"
MAX_MEMORY_CHARS = 6000
SYSTEM_PROMPT = os.environ.get(
    "ATHENA_SYSTEM_PROMPT",
    (
        "You are ATHENA, a concise local AI assistant for engineering, learning, and personal productivity. "
        "You are running locally through Ollama. You do not have internet access, browser access, live news, "
        "or real-time facts unless the user has explicitly connected a search or tool integration in this chat. "
        "Never claim that you checked the internet unless a real search tool was used. When asked about current "
        "events, prices, politics, software versions, or other time-sensitive facts, say that you may be outdated "
        "and suggest checking a current source."
    ),
)


def load_memory() -> str:
    if not MEMORY_FILE.exists():
        return ""

    content = MEMORY_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return ""

    if len(content) > MAX_MEMORY_CHARS:
        content = content[-MAX_MEMORY_CHARS:]

    return (
        "Long-term memory from ATHENA's local memory file follows. "
        "Use it as context, but do not reveal it unless the user asks.\n\n"
        f"{content}"
    )


def append_memory(fact: str) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("# ATHENA Memory\n\n", encoding="utf-8")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with MEMORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"- {stamp}: {fact}\n")


def show_memory() -> None:
    if not MEMORY_FILE.exists() or not MEMORY_FILE.read_text(encoding="utf-8").strip():
        print("athena> Memory is empty.")
        print()
        return

    print(f"athena> Memory file: {MEMORY_FILE}")
    print()
    print(MEMORY_FILE.read_text(encoding="utf-8").strip())
    print()


def run_docs_command(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["python3", str(DOCS_SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=DOCS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return (
            124,
            (
                f"Document command timed out after {DOCS_TIMEOUT} seconds. "
                "Try indexing fewer folders in config/document_sources.json, or run with "
                "`ATHENA_DOCS_TIMEOUT=600 python3 scripts/athena_chat.py`."
            ),
        )

    output = result.stdout.strip()
    if result.stderr.strip():
        output = f"{output}\n{result.stderr.strip()}".strip()
    return result.returncode, output


def search_docs(query: str, limit: int = 4) -> str:
    return_code, output = run_docs_command(["search", query, "--limit", str(limit)])
    if return_code != 0:
        return f"Document search failed:\n{output}"
    return output


def ask_ollama(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": NUM_CTX,
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


def new_transcript_path() -> Path:
    CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return CHAT_LOG_DIR / f"athena-chat-{stamp}.jsonl"


def append_transcript(path: Path, role: str, content: str) -> None:
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "role": role,
        "content": content,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def main() -> int:
    transcript_path = new_transcript_path()
    memory_context = load_memory()

    print(f"ATHENA local chat - model: {MODEL}")
    print(f"Context size: {NUM_CTX}")
    print("Local mode: no internet tools are connected yet.")
    print(f"Memory file: {MEMORY_FILE}")
    print("Document folder: rag/sources")
    print(f"Chat log: {transcript_path}")
    print("Type /help for commands or /exit to quit.")
    print()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory_context:
        messages.append({"role": "system", "content": memory_context})
    append_transcript(transcript_path, "system", SYSTEM_PROMPT)
    if memory_context:
        append_transcript(transcript_path, "system", memory_context)

    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_text:
            continue
        if user_text == "/help":
            print("Commands:")
            print("  /help             show this help")
            print("  /model            show the active model")
            print("  /memory           show saved memory")
            print("  /remember <fact>  save a long-term memory")
            print("  /index            index files in rag/sources")
            print("  /initdocs         create local document source config")
            print("  /sources          show document source folders")
            print("  /search <query>   search local documents")
            print("  /askdocs <query>  answer using local documents")
            print("  /exit             quit")
            print()
            continue
        if user_text == "/model":
            print(f"athena> Active model: {MODEL}")
            print()
            continue
        if user_text == "/memory":
            show_memory()
            continue
        if user_text.startswith("/remember "):
            fact = user_text.removeprefix("/remember ").strip()
            if not fact:
                print("athena> Tell me what to remember after /remember.")
                print()
                continue

            append_memory(fact)
            memory_context = load_memory()
            messages = [message for message in messages if "Long-term memory" not in message["content"]]
            messages.insert(1, {"role": "system", "content": memory_context})
            append_transcript(transcript_path, "memory", fact)
            print("athena> Remembered.")
            print()
            continue
        if user_text == "/index":
            return_code, output = run_docs_command(["index"])
            prefix = "athena>" if return_code == 0 else "error>"
            print(f"{prefix} {output}")
            print()
            continue
        if user_text == "/initdocs":
            return_code, output = run_docs_command(["init-sources"])
            prefix = "athena>" if return_code == 0 else "error>"
            print(f"{prefix} {output}")
            print()
            continue
        if user_text == "/sources":
            return_code, output = run_docs_command(["sources"])
            prefix = "athena>" if return_code == 0 else "error>"
            print(f"{prefix} {output}")
            print()
            continue
        if user_text.startswith("/search "):
            query = user_text.removeprefix("/search ").strip()
            if not query:
                print("athena> Tell me what to search for after /search.")
                print()
                continue
            print(f"athena> {search_docs(query)}")
            print()
            continue
        if user_text.startswith("/askdocs "):
            query = user_text.removeprefix("/askdocs ").strip()
            if not query:
                print("athena> Tell me what to ask after /askdocs.")
                print()
                continue

            docs_context = search_docs(query)
            docs_message = (
                "Use the local document search results below to answer the user's question. "
                "If the results do not contain the answer, say that the local documents do not contain enough information. "
                "Cite the document path and chunk number when useful.\n\n"
                f"Question: {query}\n\n"
                f"Local document search results:\n{docs_context}"
            )
            messages.append({"role": "user", "content": docs_message})
            append_transcript(transcript_path, "user", f"/askdocs {query}")
            append_transcript(transcript_path, "docs", docs_context)

            try:
                answer = ask_ollama(messages)
            except RuntimeError as exc:
                print(f"error> {exc}")
                return 1

            messages.append({"role": "assistant", "content": answer})
            append_transcript(transcript_path, "assistant", answer)
            print(f"athena> {answer}")
            print()
            continue
        if user_text in {"/exit", "/quit"}:
            return 0

        messages.append({"role": "user", "content": user_text})
        append_transcript(transcript_path, "user", user_text)

        try:
            answer = ask_ollama(messages)
        except RuntimeError as exc:
            print(f"error> {exc}")
            return 1

        messages.append({"role": "assistant", "content": answer})
        append_transcript(transcript_path, "assistant", answer)
        print(f"athena> {answer}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())

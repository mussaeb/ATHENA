#!/usr/bin/env python3
"""Local page for chat, voice, documents, web search, and reviewed code edits."""

from __future__ import annotations

import argparse
import json
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import athena_voice
from athena_chat import MODEL, ChatSession, command_name
from athena_code import git_diff, git_log, git_status, list_project_files, read_project_file
from athena_common import PROJECT_ROOT, load_dotenv


load_dotenv(PROJECT_ROOT)

PAGE_PATH = Path(__file__).with_name("athena_ui.html")
HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("ATHENA_UI_PORT", "8765"))
MAX_BODY = 64_000
SPOKEN_COMMANDS = {"/askdocs", "/askweb", "/recall"}
SPEECH_LOCK = threading.Lock()


class AthenaServer(ThreadingHTTPServer):
    daemon_threads = True


def page_bytes() -> bytes:
    return PAGE_PATH.read_bytes()


def wants_voice_reply(user_text: str, speak_enabled: bool) -> bool:
    if not speak_enabled:
        return False
    stripped = user_text.strip()
    if not stripped.startswith("/"):
        return True
    return command_name(stripped) in SPOKEN_COMMANDS


def speak_later(text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return

    def run() -> None:
        with SPEECH_LOCK:
            athena_voice.speak(cleaned)

    threading.Thread(target=run, daemon=True).start()


def apply_settings(session: ChatSession, data: dict) -> None:
    if "speak" in data:
        session.speak = bool(data["speak"])
    if "docmode" in data:
        session.docmode = bool(data["docmode"])
    if "webmode" in data:
        session.webmode = bool(data["webmode"])


def status_payload(session: ChatSession) -> dict[str, object]:
    return {
        "model": MODEL,
        "speak": session.speak,
        "docmode": session.docmode,
        "webmode": session.webmode,
        "session": session.session_name,
    }


def file_list_payload(query: str) -> dict[str, object]:
    text = list_project_files(PROJECT_ROOT, query, limit=80)
    files = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    return {"text": text, "files": files}


def build_handler(session: ChatSession, lock: threading.Lock | None = None) -> type[BaseHTTPRequestHandler]:
    session_lock = lock or threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send(200, "text/html; charset=utf-8", page_bytes())
                return
            if parsed.path == "/api/status":
                with session_lock:
                    payload = status_payload(session)
                self._json(200, payload)
                return
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/code/files":
                self._json(200, file_list_payload(query.get("q", [""])[0]))
                return
            if parsed.path == "/api/code/file":
                path = query.get("path", [""])[0]
                try:
                    text = read_project_file(PROJECT_ROOT, path)
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                    return
                self._json(200, {"path": path, "text": text})
                return
            if parsed.path == "/api/code/git":
                view = query.get("view", ["status"])[0]
                if view == "diff":
                    text = git_diff()
                elif view == "log":
                    text = git_log()
                else:
                    text = git_status()
                self._json(200, {"text": text})
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                data = self._read_json()
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            if parsed.path == "/api/settings":
                with session_lock:
                    apply_settings(session, data)
                    payload = status_payload(session)
                self._json(200, payload)
                return
            if parsed.path == "/api/turn":
                text = str(data.get("text", "")).strip()
                if not text:
                    self._json(400, {"error": "Type or say a message first."})
                    return
                with session_lock:
                    speak = wants_voice_reply(text, bool(session.speak))
                    try:
                        result = session.exchange(text, defer_speech=True)
                    except Exception as exc:
                        self._json(500, {"error": str(exc)})
                        return
                voiced = bool(speak and result.get("text"))
                if voiced:
                    speak_later(str(result["text"]))
                result["voiced"] = voiced
                self._json(200, result)
                return
            self._json(404, {"error": "Not found"})

        def _read_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid request size.") from exc
            if length < 0 or length > MAX_BODY:
                self.close_connection = True
                if 0 < length <= MAX_BODY + 8192:
                    self.rfile.read(length)
                raise ValueError("Request is too large.")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Expected JSON.") from exc
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            return data

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8"))

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(port: int = DEFAULT_PORT, session: ChatSession | None = None, open_browser: bool = False) -> None:
    chat = session or ChatSession()
    server = AthenaServer((HOST, port), build_handler(chat))
    url = f"http://{HOST}:{server.server_address[1]}"
    print(f"ATHENA page: {url}")
    print("Leave this window open. Stop it with Ctrl+C.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Open the local ATHENA page.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window.")
    args = parser.parse_args()
    open_browser = not args.no_open and os.environ.get("ATHENA_UI_OPEN", "1") != "0"
    try:
        serve(port=args.port, open_browser=open_browser)
    except OSError as exc:
        print(f"Could not start the page on {HOST}:{args.port}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

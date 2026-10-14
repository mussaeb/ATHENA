#!/usr/bin/env python3
"""Local page for chat, voice, documents, web search, and reviewed code edits."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import athena_voice
from athena_chat import MODEL, ChatSession, ask_ollama, command_name, propose_file_budget
from athena_code import (
    SKIPPED_DIRS,
    build_updated_text,
    git_diff,
    git_log,
    git_status,
    is_secret,
    is_writable,
    list_project_files,
    normalize_newlines,
    parse_new_file,
    parse_replacement,
    proposal_diff,
    read_project_file,
    resolve_inside,
    save_proposal,
)
from athena_common import PROJECT_ROOT, clip, load_dotenv


load_dotenv(PROJECT_ROOT)

PAGE_PATH = Path(__file__).with_name("athena_ui.html")
HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("ATHENA_UI_PORT", "8765"))
MAX_BODY = 64_000
TOKEN_PLACEHOLDER = "__ATHENA_TOKEN__"
SPOKEN_COMMANDS = {"/askdocs", "/askweb", "/recall"}
SPEECH_LOCK = threading.Lock()
TERMINAL_TIMEOUT = 60
TERMINAL_OUTPUT_LIMIT = 30_000
CD_COMMAND = re.compile(r"^cd(?:\s+(.+))?$")


class AthenaServer(ThreadingHTTPServer):
    daemon_threads = True


def render_page(token: str) -> bytes:
    html = PAGE_PATH.read_text(encoding="utf-8")
    return html.replace(TOKEN_PLACEHOLDER, token).encode("utf-8")


def list_directory(root: Path, user_path: str) -> dict[str, object]:
    root_resolved = root.resolve()
    if user_path.strip() in {"", "."}:
        target = root_resolved
        relative = Path(".")
    else:
        target = resolve_inside(root, user_path)
        relative = target.relative_to(root_resolved)
        if _hidden_or_skipped(relative):
            raise ValueError(f"Refusing to open {relative.as_posix()}.")
    if not target.is_dir():
        raise ValueError("Choose a folder to browse.")

    entries = []
    for child in target.iterdir():
        if child.name in SKIPPED_DIRS or (child.name.startswith(".") and child.name != ".gitignore"):
            continue
        try:
            child_relative = child.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        if is_secret(child_relative) or _hidden_or_skipped(child_relative):
            continue
        if child.is_dir():
            kind = "dir"
        elif child.is_file():
            kind = "file"
        else:
            continue
        entries.append({"name": child.name, "path": child_relative.as_posix(), "kind": kind})
    entries.sort(key=lambda item: (item["kind"] != "dir", item["name"].lower()))
    shown = "" if relative == Path(".") else relative.as_posix()
    parent = ""
    if relative != Path("."):
        parent = "" if relative.parent == Path(".") else relative.parent.as_posix()
    return {"path": shown, "parent": parent, "entries": entries}


def _hidden_or_skipped(relative: Path) -> bool:
    return any(part in SKIPPED_DIRS or (part.startswith(".") and part != ".gitignore") for part in relative.parts)


def project_context(root: Path, folder: str, focus: str) -> str:
    listing = list_directory(root, folder)
    shown = listing["path"] or "the whole project"
    names = [f"{'[folder] ' if item['kind'] == 'dir' else ''}{item['path']}" for item in listing["entries"][:40]]
    parts = [
        f"Scope: {shown}",
        "Git status:\n" + git_status(root),
        "Visible entries:\n" + ("\n".join(names) or "(empty folder)"),
    ]
    focus = focus.strip()
    if focus:
        try:
            preview = clip(read_project_file(root, focus), 4000)
        except ValueError as exc:
            preview = str(exc)
        parts.append(f"Open file {focus}:\n{preview}")
    return "\n\n".join(parts)


def build_project_prompt(context: str, instruction: str) -> str:
    return (
        "You are helping with one local project. Stay inside the scope below. "
        "Answer the request in plain text. "
        "If one file inside the scope should change, end with exactly one reviewed edit and do not claim it was written:\n"
        "<<<PATH>>>\nrelative/path\n<<<REPLACE>>>\nexact current text\n<<<WITH>>>\nreplacement text\n<<<END>>>\n"
        "For a new file, use <<<ATHENA_FILE>>> and <<<END>>> after <<<PATH>>> instead of REPLACE and WITH. "
        "Copy the smallest unique snippet. Do not edit secrets or files outside the scope.\n\n"
        f"{context}\n\nRequest: {instruction}"
    )


def proposal_from_model_text(
    root: Path,
    model_text: str,
    scope: str = "",
    proposal_dir: Path | None = None,
) -> dict[str, str] | None:
    if "<<<PATH>>>" not in model_text:
        return None
    relative_text = _path_marker(model_text)
    target = resolve_inside(root, relative_text)
    relative = target.relative_to(root.resolve())
    if not _inside_scope(scope, relative.as_posix()):
        raise ValueError(f"Refusing a change outside the selected folder: {relative.as_posix()}")
    if is_secret(relative) or not is_writable(relative):
        raise ValueError(f"Refusing to draft a change for {relative.as_posix()}.")
    exists = target.is_file()
    original = ""
    if exists:
        if target.stat().st_size > propose_file_budget():
            raise ValueError("That file is too large for the current context window. No file was changed.")
        original = normalize_newlines(target.read_text(encoding="utf-8", errors="replace"))
        old, new = parse_replacement(model_text)
        updated = normalize_newlines(build_updated_text(original, old, new))
    else:
        updated = normalize_newlines(parse_new_file(model_text))
    diff = proposal_diff(relative.as_posix(), original, updated)
    if diff == "No changes.":
        raise ValueError("The draft made no changes. No file was written.")
    proposal = {
        "path": relative.as_posix(),
        "instruction": "project request",
        "original": original,
        "updated": updated,
        "diff": diff,
    }
    save_proposal(proposal, proposal_dir) if proposal_dir is not None else save_proposal(proposal)
    return proposal


def ask_project(root: Path, instruction: str, folder: str = "", focus: str = "") -> dict[str, str]:
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("Tell ATHENA what to do in the project.")
    context = project_context(root, folder, focus)
    raw = ask_ollama(
        [
            {"role": "system", "content": "You revise local project files only when the requested markers are included."},
            {"role": "user", "content": build_project_prompt(context, instruction)},
        ],
        temperature=0.2,
    )
    text = raw.strip()
    try:
        proposal = proposal_from_model_text(root, raw, folder)
    except ValueError as exc:
        return {"text": text + "\n\n" + str(exc), "diff": "", "path": ""}
    if proposal is None:
        return {"text": text, "diff": "", "path": ""}
    diff = proposal["diff"]
    return {
        "text": text + "\n\n" + diff + "\n\nReview the diff above. Apply writes the file.",
        "diff": diff,
        "path": proposal["path"],
    }


def _path_marker(model_text: str) -> str:
    start = model_text.rfind("<<<PATH>>>")
    rest = model_text[start + len("<<<PATH>>>") :].strip()
    line = rest.splitlines()[0].strip() if rest else ""
    if not line or line.startswith("<<<"):
        raise ValueError("The draft did not name a file. No file was changed.")
    return line.replace("\\", "/").strip()


def _inside_scope(scope: str, relative_text: str) -> bool:
    scope = scope.strip().strip("/").replace("\\", "/")
    relative = relative_text.strip().strip("/").replace("\\", "/")
    if scope in {"", "."}:
        return True
    return relative == scope or relative.startswith(scope + "/")


class ProjectTerminal:
    """Run commands the user types. The working folder cannot leave the project."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.cwd = self.root

    def run(self, command: str) -> dict[str, object]:
        command = command.strip()
        if not command:
            raise ValueError("Type a command.")
        if len(command) > 2000 or "\n" in command or "\r" in command:
            raise ValueError("Keep the command on one line under 2000 characters.")
        destination = _cd_destination(command)
        if destination is not None:
            self.cwd = self._inside(destination)
            return {"cwd": self.location(), "text": "", "code": 0}

        try:
            result = subprocess.run(
                _shell_argv(command),
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=TERMINAL_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"cwd": self.location(), "text": f"Command timed out after {TERMINAL_TIMEOUT} seconds.", "code": 124}
        except OSError as exc:
            return {"cwd": self.location(), "text": str(exc), "code": 1}

        output = (result.stdout or "") + (result.stderr or "")
        if len(output) > TERMINAL_OUTPUT_LIMIT:
            output = output[:TERMINAL_OUTPUT_LIMIT] + "\n... output truncated"
        return {"cwd": self.location(), "text": output.strip(), "code": result.returncode}

    def location(self) -> str:
        relative = self.cwd.resolve().relative_to(self.root)
        return relative.as_posix() or "."

    def _inside(self, user_path: str) -> Path:
        if user_path in {"", "."}:
            return self.root
        candidate = Path(user_path)
        resolved = candidate.resolve() if candidate.is_absolute() else (self.cwd / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("That folder is outside the project.") from exc
        if not resolved.is_dir():
            raise ValueError("That path is not a folder in the project.")
        return resolved


def _cd_destination(command: str) -> str | None:
    if any(symbol in command for symbol in ("|", "&", ";", "<", ">")):
        return None
    match = CD_COMMAND.match(command.strip())
    if match is None:
        return None
    destination = (match.group(1) or "").strip().strip('"').strip("'")
    return destination or "."


def _shell_argv(command: str) -> list[str]:
    if sys.platform == "win32":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            raise OSError("PowerShell is not available.")
        return [powershell, "-NoProfile", "-NonInteractive", "-Command", command]
    shell = shutil.which("zsh") or shutil.which("bash") or shutil.which("sh")
    if shell is None:
        raise OSError("No local shell is available.")
    return [shell, "-c", command]


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


def build_handler(
    session: ChatSession,
    token: str = "test-token",
    lock: threading.Lock | None = None,
    terminal: ProjectTerminal | None = None,
) -> type[BaseHTTPRequestHandler]:
    session_lock = lock or threading.Lock()
    project_terminal = terminal or ProjectTerminal(PROJECT_ROOT)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send(200, "text/html; charset=utf-8", render_page(token))
                return
            if parsed.path == "/api/status":
                with session_lock:
                    payload = status_payload(session)
                self._json(200, payload)
                return
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/api/code/tree":
                try:
                    payload = list_directory(PROJECT_ROOT, query.get("path", [""])[0])
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                    return
                self._json(200, payload)
                return
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
            if not self._allowed(token):
                return
            if parsed.path == "/api/code/ask":
                instruction = str(data.get("instruction", ""))
                folder = str(data.get("path", ""))
                focus = str(data.get("focus", ""))
                with session_lock:
                    try:
                        payload = ask_project(PROJECT_ROOT, instruction, folder, focus)
                    except (OSError, ValueError, RuntimeError) as exc:
                        self._json(400, {"error": str(exc)})
                        return
                self._json(200, payload)
                return
            if parsed.path == "/api/terminal":
                command = str(data.get("command", ""))
                with session_lock:
                    try:
                        payload = project_terminal.run(command)
                    except ValueError as exc:
                        self._json(400, {"error": str(exc)})
                        return
                self._json(200, payload)
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

        def _allowed(self, expected: str) -> bool:
            supplied = self.headers.get("X-Athena-Token", "")
            if supplied and supplied == expected:
                return True
            self._json(403, {"error": "Open this action from the local ATHENA page."})
            return False

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
    token = secrets.token_hex(16)
    server = AthenaServer((HOST, port), build_handler(chat, token))
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

#!/usr/bin/env python3
"""Terminal chat client for a local Ollama model."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from athena_agent import (
    approve_next,
    default_runner,
    format_plan,
    format_tools,
    load_current_plan,
    parse_plan,
    plan_prompt,
    reject_next,
    save_plan,
)
from athena_code import (
    apply_proposal,
    build_updated_text,
    is_secret,
    is_writable,
    load_latest_proposal,
    normalize_newlines,
    parse_new_file,
    parse_replacement,
    proposal_diff,
    resolve_inside,
    save_proposal,
)
from athena_common import PROJECT_ROOT, append_safety_log, clip, load_dotenv
from athena_history import slugify, transcript_filename


load_dotenv(PROJECT_ROOT)

MODEL = os.environ.get("ATHENA_MODEL", "qwen2.5:1.5b")
OLLAMA_URL = os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
NUM_CTX = int(os.environ.get("ATHENA_NUM_CTX", "1536"))
MAX_HISTORY_MESSAGES = int(os.environ.get("ATHENA_HISTORY_MESSAGES", "8"))
DOCS_TIMEOUT = int(os.environ.get("ATHENA_DOCS_TIMEOUT", "300"))
CHAT_LOG_DIR = PROJECT_ROOT / "logs" / "chats"
MEMORY_FILE = PROJECT_ROOT / "memory" / "profile.md"
SCRIPTS = PROJECT_ROOT / "scripts"
DOCS_SCRIPT = SCRIPTS / "athena_docs.py"
WEB_SCRIPT = SCRIPTS / "athena_web.py"
VOICE_SCRIPT = SCRIPTS / "athena_voice.py"
HISTORY_SCRIPT = SCRIPTS / "athena_history.py"
CODE_SCRIPT = SCRIPTS / "athena_code.py"
INFRA_SCRIPT = SCRIPTS / "athena_infra.py"
VISION_SCRIPT = SCRIPTS / "athena_vision.py"
MAX_MEMORY_CHARS = 6000
MEMORY_HEADER = "Long-term memory from ATHENA's local memory file follows."
DEFAULT_SYSTEM_PROMPT = (
    "You are ATHENA, a concise local AI assistant for engineering, learning, and personal productivity. "
    "You run locally through Ollama. You do not have live information unless the current user message "
    "contains a section titled 'Local document search results:', 'Web search results:', or "
    "'Earlier conversation matches:'. Use only those sections for cited facts. "
    "Never claim that you checked the internet, documents, or past chats unless that section is present. "
    "If asked for current events, prices, versions, or other time-sensitive facts and no web results are attached, "
    "say that you need /askweb or /webmode on. Do not invent personal details, file contents, or command output."
)
SYSTEM_PROMPT = os.environ.get("ATHENA_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)
COMMAND_NAMES = frozenset(
    {
        "/apply",
        "/approve",
        "/askdocs",
        "/askweb",
        "/diff",
        "/docker",
        "/docmode",
        "/exit",
        "/files",
        "/findfile",
        "/git",
        "/help",
        "/history",
        "/index",
        "/infra",
        "/initdocs",
        "/jenkins",
        "/k8s",
        "/kubernetes",
        "/listen",
        "/log",
        "/memory",
        "/model",
        "/name",
        "/openstack",
        "/plan",
        "/propose",
        "/quit",
        "/read",
        "/recall",
        "/reject",
        "/remember",
        "/say",
        "/search",
        "/see",
        "/sessions",
        "/sources",
        "/speak",
        "/status",
        "/test",
        "/tools",
        "/ui",
        "/web",
        "/webmode",
    }
)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def command_name(user_text: str) -> str:
    return user_text.split(maxsplit=1)[0].lower()


def args_of(user_text: str) -> str:
    parts = user_text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def is_known_command(user_text: str) -> bool:
    return command_name(user_text) in COMMAND_NAMES


def propose_file_budget(num_ctx: int = NUM_CTX) -> int:
    return max(400, num_ctx * 2)


def secret_memory_warning(fact: str) -> str | None:
    if re.search(r"\b(password|api[_ -]?key|secret key|ssh key)\b", fact, re.I):
        return (
            "Saved in memory/profile.md, which can be committed. "
            "Put secrets in memory/private.md instead. That file is gitignored and is not loaded into chat."
        )
    return None


def help_text() -> str:
    return """Commands:
  /help                     show this help
  /model                    show model, modes, and session
  /status                   same snapshot as /model
  /exit                     quit

Memory and history:
  /memory                   show saved memory
  /remember <fact>          save a long-term memory
  /sessions                 list saved chats
  /name <session>           name the current chat
  /history <query>          search saved chats
  /recall <query>           answer using saved chats

Documents:
  /index                    index configured folders
  /initdocs                 create local document source config
  /sources                  show document source folders
  /docmode on|off           use documents for normal questions
  /findfile <name>          find source files by filename
  /search <query>           search local documents
  /askdocs <query>          answer using local documents

Web:
  /web <query>              search the web and show sources
  /askweb <query>           answer using web results
  /webmode on|off           use web search for normal questions

Voice and vision:
  /speak on|off             speak replies with the operating system voice
  /say <text>               speak one line
  /listen                   hear one utterance, then answer
  /ui                       show how to open the local page
  /see <image> <question>   describe an image when ATHENA_VISION_MODEL is set

Code:
  /git                      show git status
  /diff                     show git diff summary
  /log                      show recent commits
  /read <path>              read a project file
  /files <query>            list matching project files
  /test                     run unit tests
  /propose <path> <change>  draft a reviewed edit
  /apply yes                write the latest reviewed edit

Infrastructure and plans:
  /infra                    read-only Docker, Kubernetes, Jenkins, and OpenStack status
  /docker                   Docker status
  /k8s                      Kubernetes pod status
  /jenkins                  Jenkins job status
  /openstack                OpenStack server status
  /tools                    list the steps a plan is allowed to run
  /plan <task>              draft an allowlisted plan
  /approve                  run the next plan step
  /reject                   skip the next plan step"""


def build_grounded_message(
    query: str,
    docs_context: str | None = None,
    web_context: str | None = None,
    history_context: str | None = None,
) -> str:
    sections = []
    if docs_context is not None:
        sections.append(f"Local document search results:\n{docs_context}")
    if web_context is not None:
        sections.append(f"Web search results:\n{web_context}")
    if history_context is not None:
        sections.append(f"Earlier conversation matches:\n{history_context}")
    if not sections:
        return query

    return (
        "Answer the user's question using only the tool results below. "
        "If a result says the search failed or nothing matched, say that plainly. "
        "Cite a document path, chat file, or URL when you use a result. "
        "Do not claim you used a tool whose section is missing.\n\n"
        f"Question: {query}\n\n" + "\n\n".join(sections)
    )


def model_messages(messages: list[dict[str, str]], limit: int | None = None) -> list[dict[str, str]]:
    window = MAX_HISTORY_MESSAGES if limit is None else limit
    system = [message for message in messages if message["role"] == "system"]
    rest = [message for message in messages if message["role"] != "system"]
    kept = rest[-window:] if window > 0 else []
    return system + kept


def ask_ollama(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    num_predict: int | None = None,
) -> str:
    options: dict[str, float | int] = {"num_ctx": NUM_CTX, "temperature": temperature}
    if num_predict is not None:
        options["num_predict"] = num_predict

    payload = {
        "model": MODEL,
        "messages": model_messages(messages),
        "stream": False,
        "options": options,
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
    except TimeoutError as exc:
        raise RuntimeError("Ollama took too long to answer. Try ATHENA_NUM_CTX=1024 or a smaller model.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned a response that was not JSON.") from exc

    content = data.get("message", {}).get("content")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {data}")
    return content.strip()


def load_memory() -> str:
    if not MEMORY_FILE.exists():
        return ""

    content = MEMORY_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return ""
    if len(content) > MAX_MEMORY_CHARS:
        content = content[-MAX_MEMORY_CHARS:]
    return (
        f"{MEMORY_HEADER} "
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


def run_tool(
    script: Path,
    args: list[str],
    stdin: str | None = None,
    timeout: int = 60,
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            input=stdin,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds."
    except OSError as exc:
        return 1, "", str(exc)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class ChatSession:
    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or CHAT_LOG_DIR
        self.docmode = env_flag("ATHENA_DOCMODE")
        self.webmode = env_flag("ATHENA_WEBMODE")
        self.speak = env_flag("ATHENA_SPEAK")
        self.session_name = "chat"
        self.session_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.transcript_path = self.log_dir / transcript_filename(self.session_stamp, self.session_name)
        self._log_started = False
        self.messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        memory_context = load_memory()
        if memory_context:
            self.messages.append({"role": "system", "content": memory_context})

    def banner(self) -> str:
        return "\n".join(
            [
                f"ATHENA local chat - model: {MODEL}",
                f"Context size: {NUM_CTX}",
                f"Memory file: {MEMORY_FILE}",
                "Document folder: rag/sources",
                f"Document mode: {'on' if self.docmode else 'off'}. Use /docmode on to search docs for normal questions.",
                f"Web mode: {'on' if self.webmode else 'off'}. Use /web, /askweb, or /webmode on for live sources.",
                f"Speech: {'on' if self.speak else 'off'}. Use /speak on to hear replies.",
                "Local page: python3 scripts/athena_ui.py  then open http://127.0.0.1:8765",
                f"Chat log: {self.transcript_path}",
                "Type /help for commands or /exit to quit.",
            ]
        )

    def status_text(self) -> str:
        plan = "saved" if (PROJECT_ROOT / "logs" / "plans" / "current.json").exists() else "none"
        return "\n".join(
            [
                f"Active model: {MODEL}",
                f"Context size: {NUM_CTX}",
                f"Document mode: {'on' if self.docmode else 'off'}",
                f"Web mode: {'on' if self.webmode else 'off'}",
                f"Speech: {'on' if self.speak else 'off'}",
                f"Session: {self.session_name}",
                f"Chat log: {self.transcript_path}",
                f"Agent plan: {plan}",
            ]
        )

    def reply(self, text: str, prefix: str = "athena>") -> None:
        captured = getattr(self, "_turn_replies", None)
        if captured is not None:
            captured.append(text)
        print(f"{prefix} {text}")
        print()

    def exchange(self, user_text: str, *, defer_speech: bool = False) -> dict[str, object]:
        self._turn_replies = []
        saved_speak = self.speak
        if defer_speech:
            self.speak = False
        action = "continue"
        try:
            action = self.handle(user_text)
        finally:
            replies = list(self._turn_replies)
            self._turn_replies = None
            self.speak = saved_speak
        return {
            "text": "\n\n".join(replies).strip(),
            "exit": action == "exit",
            "speak": self.speak,
            "docmode": self.docmode,
            "webmode": self.webmode,
            "session": self.session_name,
            "model": MODEL,
        }

    def append_transcript(self, role: str, content: str) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model": MODEL,
            "session": self.session_name,
            "role": role,
            "content": content,
        }
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def ensure_log(self) -> None:
        if self._log_started:
            return
        self._log_started = True
        self.append_transcript("system", SYSTEM_PROMPT)
        memory = next((message["content"] for message in self.messages if message["content"].startswith(MEMORY_HEADER)), "")
        if memory:
            self.append_transcript("system", memory)

    def replace_memory(self, memory_context: str) -> None:
        self.messages = [message for message in self.messages if not message["content"].startswith(MEMORY_HEADER)]
        if memory_context:
            insert_at = 1 if self.messages and self.messages[0]["role"] == "system" else 0
            self.messages.insert(insert_at, {"role": "system", "content": memory_context})

    def show_tool_result(self, code: int, stdout: str, stderr: str) -> None:
        output = stdout.strip()
        if code != 0:
            output = "\n".join(part for part in (output, stderr.strip()) if part)
        elif not output:
            output = stderr.strip()
        self.reply(output or "(no output)", prefix="athena>" if code == 0 else "error>")

    def show_simple_tool(self, script: Path, args: list[str], timeout: int = 60) -> str:
        code, stdout, stderr = run_tool(script, args, timeout=timeout)
        self.show_tool_result(code, stdout, stderr)
        return "continue"

    def captured_tool(self, script: Path, args: list[str], timeout: int = 60) -> str:
        code, stdout, stderr = run_tool(script, args, timeout=timeout)
        if code == 0:
            return stdout or stderr or "(no output)"
        return "\n".join(part for part in (stdout, stderr) if part.strip()) or "Tool failed."

    def speak_answer(self, text: str) -> None:
        if not self.speak:
            return
        code, stdout, stderr = run_tool(VOICE_SCRIPT, ["speak"], stdin=text, timeout=120)
        if code != 0:
            self.speak = False
            self.reply(f"Speech failed, so I turned it off. {stderr or stdout or 'speech failed'}")

    def complete_turn(self, content: str) -> str:
        self.messages.append({"role": "user", "content": content})
        try:
            answer = ask_ollama(self.messages)
        except RuntimeError:
            self.messages.pop()
            raise
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def finish_answer(self, answer: str, contexts: list[tuple[str, str]]) -> None:
        for role, content in contexts:
            self.append_transcript(role, content)
        self.append_transcript("assistant", answer)
        self.reply(answer)
        self.speak_answer(answer)

    def grounded_answer(
        self,
        query: str,
        transcript_user: str,
        use_docs: bool,
        use_web: bool,
        use_history: bool,
    ) -> None:
        labels = []
        if use_docs:
            labels.append("documents")
        if use_web:
            labels.append("the web")
        if use_history:
            labels.append("saved chats")
        if labels:
            print("athena> Searching " + " and ".join(labels) + "...")

        docs_context = self.captured_tool(DOCS_SCRIPT, ["search", query, "--limit", "4"], timeout=120) if use_docs else None
        web_context = self.captured_tool(WEB_SCRIPT, ["search", query, "--limit", "4"], timeout=30) if use_web else None
        history_context = (
            self.captured_tool(HISTORY_SCRIPT, ["search", query, "--limit", "5"], timeout=30) if use_history else None
        )
        prompt = build_grounded_message(
            query,
            docs_context=docs_context,
            web_context=web_context,
            history_context=history_context,
        )
        self.ensure_log()
        self.append_transcript("user", transcript_user)
        try:
            answer = self.complete_turn(prompt)
        except RuntimeError as exc:
            self.reply(str(exc), prefix="error>")
            return

        contexts = []
        if docs_context is not None:
            contexts.append(("docs", docs_context))
        if web_context is not None:
            contexts.append(("web", web_context))
        if history_context is not None:
            contexts.append(("history", history_context))
        self.finish_answer(answer, contexts)

    def answer_freeform(self, user_text: str) -> None:
        if self.docmode or self.webmode:
            self.grounded_answer(user_text, user_text, self.docmode, self.webmode, False)
            return

        self.ensure_log()
        self.append_transcript("user", user_text)
        try:
            answer = self.complete_turn(user_text)
        except RuntimeError as exc:
            self.reply(str(exc), prefix="error>")
            return
        self.finish_answer(answer, [])

    def require_arg(self, user_text: str, hint: str) -> str | None:
        value = args_of(user_text)
        if value:
            return value
        self.reply(hint)
        return None

    def set_mode(
        self,
        user_text: str,
        current: bool,
        command: str,
        on_message: str,
        off_message: str,
        label: str,
    ) -> bool | None:
        arg = args_of(user_text).lower()
        if arg in {"on", "true"}:
            self.reply(on_message)
            return True
        if arg in {"off", "false"}:
            self.reply(off_message)
            return False
        state = "on" if current else "off"
        self.reply(f"{label} is {state}. Use /{command} on or /{command} off.")
        return None

    def handle_help(self, user_text: str) -> str:
        print(help_text())
        print()
        return "continue"

    def handle_model(self, user_text: str) -> str:
        self.reply(self.status_text())
        return "continue"

    def handle_exit(self, user_text: str) -> str:
        return "exit"

    def handle_memory(self, user_text: str) -> str:
        show_memory()
        return "continue"

    def handle_remember(self, user_text: str) -> str:
        fact = self.require_arg(user_text, "Tell me what to remember after /remember.")
        if fact is None:
            return "continue"
        append_memory(fact)
        self.replace_memory(load_memory())
        self.ensure_log()
        self.append_transcript("memory", fact)
        warning = secret_memory_warning(fact)
        self.reply("Remembered. " + warning if warning else "Remembered.")
        return "continue"

    def handle_sessions(self, user_text: str) -> str:
        return self.show_simple_tool(HISTORY_SCRIPT, ["list"])

    def handle_name(self, user_text: str) -> str:
        name = args_of(user_text)
        if not name:
            self.reply(f"Session name: {self.session_name}")
            return "continue"

        self.ensure_log()
        new_path = self.log_dir / transcript_filename(self.session_stamp, name)
        if new_path != self.transcript_path and new_path.exists():
            new_path = self.log_dir / f"athena-{self.session_stamp}-{slugify(name)}-2.jsonl"
        if new_path != self.transcript_path:
            self.transcript_path.rename(new_path)
            self.transcript_path = new_path
        self.session_name = name
        self.append_transcript("session", name)
        self.reply(f"Session name: {name}")
        return "continue"

    def handle_history(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to look for after /history.")
        if query is None:
            return "continue"
        return self.show_simple_tool(HISTORY_SCRIPT, ["search", query])

    def handle_recall(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to recall after /recall.")
        if query is None:
            return "continue"
        self.grounded_answer(query, f"/recall {query}", False, False, True)
        return "continue"

    def handle_index(self, user_text: str) -> str:
        print("athena> Indexing documents...")
        return self.show_simple_tool(DOCS_SCRIPT, ["index"], timeout=DOCS_TIMEOUT)

    def handle_initdocs(self, user_text: str) -> str:
        return self.show_simple_tool(DOCS_SCRIPT, ["init-sources"])

    def handle_sources(self, user_text: str) -> str:
        return self.show_simple_tool(DOCS_SCRIPT, ["sources"])

    def handle_docmode(self, user_text: str) -> str:
        updated = self.set_mode(
            user_text,
            self.docmode,
            "docmode",
            "Document mode is on. Normal questions will use local document search.",
            "Document mode is off. Use /askdocs when you want document-backed answers.",
            "Document mode",
        )
        if updated is not None:
            self.docmode = updated
        return "continue"

    def handle_findfile(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to find after /findfile.")
        if query is None:
            return "continue"
        return self.show_simple_tool(DOCS_SCRIPT, ["findfile", query])

    def handle_search(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to search for after /search.")
        if query is None:
            return "continue"
        return self.show_simple_tool(DOCS_SCRIPT, ["search", query, "--limit", "4"])

    def handle_askdocs(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to ask after /askdocs.")
        if query is None:
            return "continue"
        self.grounded_answer(query, f"/askdocs {query}", True, False, False)
        return "continue"

    def handle_web(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to look up after /web.")
        if query is None:
            return "continue"
        return self.show_simple_tool(WEB_SCRIPT, ["search", query, "--limit", "5"], timeout=30)

    def handle_askweb(self, user_text: str) -> str:
        query = self.require_arg(user_text, "Tell me what to ask after /askweb.")
        if query is None:
            return "continue"
        self.grounded_answer(query, f"/askweb {query}", False, True, False)
        return "continue"

    def handle_webmode(self, user_text: str) -> str:
        updated = self.set_mode(
            user_text,
            self.webmode,
            "webmode",
            "Web mode is on. Normal questions will include web search results and sources.",
            "Web mode is off. Use /askweb when you want a web-backed answer.",
            "Web mode",
        )
        if updated is not None:
            self.webmode = updated
        return "continue"

    def handle_ui(self, user_text: str) -> str:
        self.reply(
            "The local page is a separate process. From the ATHENA folder run: "
            "python3 scripts/athena_ui.py  then open http://127.0.0.1:8765. "
            "On Windows, use python instead of python3. "
            "Listen on that page uses the browser microphone. Speak replies uses the operating system voice."
        )
        return "continue"

    def handle_speak(self, user_text: str) -> str:
        arg = args_of(user_text).lower()
        if arg in {"on", "true"}:
            self.speak = True
            self.reply("Speech is on. Replies will be read aloud.")
            self.speak_answer("Speech is on.")
            return "continue"
        if arg in {"off", "false"}:
            self.speak = False
            self.reply("Speech is off.")
            return "continue"
        state = "on" if self.speak else "off"
        self.reply(f"Speech is {state}. Use /speak on or /speak off.")
        return "continue"

    def handle_say(self, user_text: str) -> str:
        text = self.require_arg(user_text, "Use /say <text>.")
        if text is None:
            return "continue"
        code, stdout, stderr = run_tool(VOICE_SCRIPT, ["speak"], stdin=text, timeout=120)
        if code != 0:
            self.reply(stderr or stdout or "Speech failed.", prefix="error>")
        else:
            self.reply("Spoken.")
        return "continue"

    def handle_listen(self, user_text: str) -> str:
        print("athena> Listening. Speak, then pause.")
        code, stdout, stderr = run_tool(VOICE_SCRIPT, ["listen"], timeout=30)
        if code != 0 or not stdout.strip():
            self.reply(stderr.strip() or stdout.strip() or "No speech recognized.")
            return "continue"
        utterance = stdout.strip()
        print(f"you> {utterance}")
        self.answer_freeform(utterance)
        return "continue"

    def handle_see(self, user_text: str) -> str:
        body = args_of(user_text)
        parts = body.split(maxsplit=1)
        if not parts:
            self.reply("Use /see <image> <question>. Example: /see screenshot.png What error is shown?")
            return "continue"
        image = parts[0]
        question = parts[1] if len(parts) > 1 else "Describe this image."
        print("athena> Looking at the image...")
        code, stdout, stderr = run_tool(VISION_SCRIPT, [image, question], timeout=180)
        self.show_tool_result(code, stdout, stderr)
        if code == 0 and stdout.strip():
            description = stdout.strip()
            self.ensure_log()
            self.append_transcript("user", f"/see {image} {question}")
            self.append_transcript("assistant", description)
            self.messages.append({"role": "user", "content": f"/see {image} {question}"})
            self.messages.append({"role": "assistant", "content": clip(description, 4000)})
            if not description.startswith("Vision is not enabled."):
                self.speak_answer(description)
        return "continue"

    def handle_git(self, user_text: str) -> str:
        arg = args_of(user_text).lower()
        if arg in {"", "status"}:
            return self.show_simple_tool(CODE_SCRIPT, ["git-status"])
        if arg == "diff":
            return self.handle_diff(user_text)
        if arg == "log":
            return self.handle_log(user_text)
        self.reply("Use /git, /git diff, or /git log.")
        return "continue"

    def handle_diff(self, user_text: str) -> str:
        return self.show_simple_tool(CODE_SCRIPT, ["git-diff"])

    def handle_log(self, user_text: str) -> str:
        return self.show_simple_tool(CODE_SCRIPT, ["git-log"])

    def handle_read(self, user_text: str) -> str:
        path = self.require_arg(user_text, "Use /read <path>. Example: /read README.md")
        if path is None:
            return "continue"
        return self.show_simple_tool(CODE_SCRIPT, ["read", path])

    def handle_files(self, user_text: str) -> str:
        query = args_of(user_text)
        args = ["files", query] if query else ["files"]
        return self.show_simple_tool(CODE_SCRIPT, args)

    def handle_test(self, user_text: str) -> str:
        print("athena> Running unit tests...")
        return self.show_simple_tool(CODE_SCRIPT, ["test"], timeout=180)

    def handle_propose(self, user_text: str) -> str:
        body = args_of(user_text)
        parts = body.split(maxsplit=1)
        if len(parts) < 2:
            self.reply("Use /propose <path> <instruction>. Example: /propose README.md Mention the voice commands.")
            return "continue"

        relative_text, instruction = parts
        try:
            target = resolve_inside(PROJECT_ROOT, relative_text)
            relative = target.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            self.reply(f"That path is outside the project: {relative_text}", prefix="error>")
            return "continue"
        if is_secret(relative) or not is_writable(relative):
            self.reply(f"Refusing to draft a change for {relative.as_posix()}.", prefix="error>")
            return "continue"

        exists = target.is_file()
        original = ""
        if exists:
            if target.stat().st_size > 1_000_000:
                self.reply("That file is too large to revise here.", prefix="error>")
                return "continue"
            original = target.read_text(encoding="utf-8", errors="replace")
            budget = propose_file_budget()
            if len(original) > budget:
                self.reply(
                    "That file is too large for the current context window. "
                    f"It has {len(original)} characters and the budget is {budget}. "
                    "Raise ATHENA_NUM_CTX, or ask for a change in a smaller file."
                )
                return "continue"
            prompt = (
                "Edit the file by replacing one exact snippet. Return only this shape:\n"
                "<<<REPLACE>>>\nexact current text\n<<<WITH>>>\nreplacement text\n<<<END>>>\n"
                "Copy the smallest unique snippet from the current file. Do not add explanations.\n\n"
                f"Path: {relative.as_posix()}\nInstruction: {instruction}\n\nCurrent file:\n{original}"
            )
        else:
            prompt = (
                "Create the file. Return only this shape:\n"
                "<<<ATHENA_FILE>>>\nfull file contents\n<<<END>>>\n"
                "Do not add explanations.\n\n"
                f"Path: {relative.as_posix()}\nInstruction: {instruction}"
            )

        print("athena> Drafting a reviewed change. Nothing will be written yet.")
        try:
            raw = ask_ollama(
                [
                    {"role": "system", "content": "You revise local text files and return only the requested markers."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                num_predict=min(800, max(200, NUM_CTX // 2)),
            )
        except RuntimeError as exc:
            self.reply(str(exc), prefix="error>")
            return "continue"

        try:
            if exists:
                old, new = parse_replacement(raw)
                updated = build_updated_text(original, old, new)
                original_norm = normalize_newlines(original)
            else:
                updated = parse_new_file(raw)
                original_norm = ""
        except ValueError as exc:
            self.reply(str(exc), prefix="error>")
            return "continue"

        updated_norm = normalize_newlines(updated)
        diff = proposal_diff(relative.as_posix(), original_norm, updated_norm)
        if diff == "No changes.":
            self.reply("The draft made no changes. No file was written.")
            return "continue"

        save_proposal(
            {
                "path": relative.as_posix(),
                "instruction": instruction,
                "original": original_norm,
                "updated": updated_norm,
                "diff": diff,
                "created": datetime.now().isoformat(timespec="seconds"),
            }
        )
        append_safety_log("propose", f"{relative.as_posix()}\n{diff}", approved=False)
        self.ensure_log()
        self.append_transcript("proposal", diff)
        self.reply(diff + "\n\nReview the diff above. Apply it with /apply yes")
        return "continue"

    def handle_apply(self, user_text: str) -> str:
        try:
            proposal = load_latest_proposal()
        except ValueError as exc:
            self.reply(str(exc), prefix="error>")
            return "continue"
        if args_of(user_text).lower() != "yes":
            diff = str(proposal.get("diff", ""))
            self.reply(f"Latest proposal is for {proposal.get('path', 'unknown file')}. Run /apply yes to write it.\n\n{diff}")
            return "continue"
        try:
            message = apply_proposal(PROJECT_ROOT, proposal)
        except (OSError, ValueError) as exc:
            self.reply(str(exc), prefix="error>")
            return "continue"
        self.reply(message)
        return "continue"

    def handle_infra(self, user_text: str) -> str:
        print("athena> Checking infrastructure. Missing tools are reported and skipped.")
        return self.show_simple_tool(INFRA_SCRIPT, ["status"], timeout=40)

    def handle_docker(self, user_text: str) -> str:
        return self.show_simple_tool(INFRA_SCRIPT, ["docker"], timeout=20)

    def handle_k8s(self, user_text: str) -> str:
        return self.show_simple_tool(INFRA_SCRIPT, ["kubernetes"], timeout=20)

    def handle_jenkins(self, user_text: str) -> str:
        return self.show_simple_tool(INFRA_SCRIPT, ["jenkins"], timeout=20)

    def handle_openstack(self, user_text: str) -> str:
        return self.show_simple_tool(INFRA_SCRIPT, ["openstack"], timeout=25)

    def handle_tools(self, user_text: str) -> str:
        self.reply(format_tools())
        return "continue"

    def handle_plan(self, user_text: str) -> str:
        goal = args_of(user_text)
        if not goal or goal == "status":
            plan = load_current_plan()
            self.reply(format_plan(plan) if plan else "No plan yet. Use /plan <task>.")
            return "continue"

        print("athena> Drafting a plan. Nothing will run until you /approve a step.")
        try:
            raw = ask_ollama(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": plan_prompt(goal)},
                ],
                temperature=0.2,
            )
        except RuntimeError as exc:
            self.reply(str(exc), prefix="error>")
            return "continue"

        plan = parse_plan(goal, raw)
        if not plan["steps"] and not plan["rejected"]:
            self.reply("I could not find an allowlisted plan in the model reply.\n" + clip(raw, 1200), prefix="error>")
            return "continue"
        save_plan(plan)
        self.ensure_log()
        self.append_transcript("user", f"/plan {goal}")
        self.append_transcript("plan", format_plan(plan))
        self.reply(format_plan(plan))
        return "continue"

    def handle_approve(self, user_text: str) -> str:
        plan = load_current_plan()
        if plan is None:
            self.reply("No plan yet. Use /plan <task>.")
            return "continue"
        print("athena> Running the next approved step...")
        message, updated = approve_next(plan, default_runner)
        save_plan(updated)
        self.ensure_log()
        self.append_transcript("tool", message)
        self.messages.append({"role": "assistant", "content": clip(message, 4000)})
        self.reply(message)
        return "continue"

    def handle_reject(self, user_text: str) -> str:
        plan = load_current_plan()
        if plan is None:
            self.reply("No plan yet. Use /plan <task>.")
            return "continue"
        message, updated = reject_next(plan)
        save_plan(updated)
        self.reply(message)
        return "continue"

    def command_handlers(self) -> dict:
        return {
            "/apply": self.handle_apply,
            "/approve": self.handle_approve,
            "/askdocs": self.handle_askdocs,
            "/askweb": self.handle_askweb,
            "/diff": self.handle_diff,
            "/docker": self.handle_docker,
            "/docmode": self.handle_docmode,
            "/exit": self.handle_exit,
            "/files": self.handle_files,
            "/findfile": self.handle_findfile,
            "/git": self.handle_git,
            "/help": self.handle_help,
            "/history": self.handle_history,
            "/index": self.handle_index,
            "/infra": self.handle_infra,
            "/initdocs": self.handle_initdocs,
            "/jenkins": self.handle_jenkins,
            "/k8s": self.handle_k8s,
            "/kubernetes": self.handle_k8s,
            "/listen": self.handle_listen,
            "/log": self.handle_log,
            "/memory": self.handle_memory,
            "/model": self.handle_model,
            "/name": self.handle_name,
            "/openstack": self.handle_openstack,
            "/plan": self.handle_plan,
            "/propose": self.handle_propose,
            "/quit": self.handle_exit,
            "/read": self.handle_read,
            "/recall": self.handle_recall,
            "/reject": self.handle_reject,
            "/remember": self.handle_remember,
            "/say": self.handle_say,
            "/search": self.handle_search,
            "/see": self.handle_see,
            "/sessions": self.handle_sessions,
            "/sources": self.handle_sources,
            "/speak": self.handle_speak,
            "/status": self.handle_model,
            "/test": self.handle_test,
            "/tools": self.handle_tools,
            "/ui": self.handle_ui,
            "/web": self.handle_web,
            "/webmode": self.handle_webmode,
        }

    def handle(self, user_text: str) -> str:
        if user_text.startswith("/"):
            handler = self.command_handlers().get(command_name(user_text))
            if handler is None:
                self.reply("Unknown command. Type /help to see available commands.")
                return "continue"
            return handler(user_text)
        self.answer_freeform(user_text)
        return "continue"

    def run(self) -> int:
        self.ensure_log()
        print(self.banner())
        print()
        while True:
            try:
                user_text = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user_text:
                continue
            try:
                if self.handle(user_text) == "exit":
                    return 0
            except KeyboardInterrupt:
                print()
                self.reply("Stopped the current step. You are still in the chat.")


def main() -> int:
    return ChatSession().run()


if __name__ == "__main__":
    raise SystemExit(main())

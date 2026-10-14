#!/usr/bin/env python3
"""Check whether this machine can run the local ATHENA scripts."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from athena_common import PROJECT_ROOT, load_dotenv


load_dotenv(PROJECT_ROOT)


def command_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip() or result.stderr.strip()


def check_command(name: str, command: list[str], required: bool) -> bool:
    path = shutil.which(command[0])
    label = "required" if required else "optional"
    if not path:
        print(f"[missing] {name} ({label})")
        return False

    version = command_output(command)
    suffix = f" - {version.splitlines()[0]}" if version else ""
    print(f"[ok] {name}: {path}{suffix}")
    return True


def physical_memory_gib() -> float | None:
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return status.ullTotalPhys / (1024**3)

        if sys.platform == "darwin":
            raw = command_output(["sysctl", "-n", "hw.memsize"])
            if raw and raw.isdigit():
                return int(raw) / (1024**3)
    except (AttributeError, OSError, ValueError):
        return None
    return None


def ollama_url() -> str:
    return os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def check_ollama_api() -> None:
    try:
        with urllib.request.urlopen(f"{ollama_url()}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, ValueError):
        print("[info] Ollama API is not responding yet. Open Ollama, then try again.")
        return

    names = [str(item.get("name", "")) for item in payload.get("models", []) if isinstance(item, dict)]
    print("[ok] Ollama API is responding")
    if names:
        print("[info] Installed models: " + ", ".join(name for name in names[:8] if name))
    else:
        print("[info] No models pulled yet. Run: ollama pull qwen2.5:1.5b")


def compile_scripts() -> bool:
    import py_compile

    print()
    print("Script compile check")
    ok = True
    for path in sorted((PROJECT_ROOT / "scripts").glob("athena_*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            print(f"[fail] {path.name}: {exc.msg}")
            ok = False
        else:
            print(f"[ok] {path.name}")
    return ok


def check_project_files() -> bool:
    expected = [
        "README.md",
        "memory/profile.md",
        "rag/sources/athena-overview.md",
        "scripts/athena_chat.py",
        "scripts/athena_docs.py",
        "scripts/athena_history.py",
        "scripts/athena_web.py",
        "scripts/athena_voice.py",
        "scripts/athena_listen_mac.swift",
        "scripts/athena_ui.py",
        "scripts/athena_ui.html",
        "scripts/athena_code.py",
        "scripts/athena_infra.py",
        "scripts/athena_agent.py",
        "scripts/athena_vision.py",
        "tests",
    ]
    print()
    print("Project files")
    ok = True
    for relative in expected:
        path = PROJECT_ROOT / relative
        if path.exists():
            print(f"[ok] {relative}")
        else:
            print(f"[missing] {relative}")
            ok = False
    return ok


def python_launcher() -> str:
    return Path(sys.executable).stem


def main() -> int:
    print("ATHENA local readiness check")
    print()
    print(f"[info] OS: {platform.system()} {platform.release()}")
    print(f"[info] CPU architecture: {platform.machine()}")
    if platform.system() == "Darwin" and platform.machine() != "arm64":
        print("[warn] The Mac setup guide is tuned for Apple Silicon.")
    elif platform.system() != "Darwin":
        print("[info] The setup guide is written for an 8 GB Apple Silicon Mac. These scripts also run here.")

    memory = physical_memory_gib()
    if memory is not None:
        print(f"[info] Physical memory: {memory:.1f} GB")
        if memory <= 12:
            print("[info] Keep to one small Ollama model. Leave Docker and extra browsers closed while chatting.")

    print(f"[ok] Python: {sys.executable} - {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        print("[fail] ATHENA needs Python 3.9 or newer.")
        return 1
    print()

    check_command("Git", ["git", "--version"], required=False)
    check_command("Ollama", ["ollama", "--version"], required=False)
    check_command("Docker", ["docker", "--version"], required=False)
    check_command("kubectl", ["kubectl", "version", "--client"], required=False)
    check_command("pdftotext", ["pdftotext", "-v"], required=False)
    if platform.system() == "Darwin":
        check_command("say", ["say", "-v", "?"], required=False)
    else:
        check_command("PowerShell", ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], required=False)

    print()
    if shutil.which("ollama"):
        check_ollama_api()
    else:
        print("[info] Ollama is optional until you want local chat. Install it from https://ollama.com/download")

    files_ok = check_project_files()
    scripts_ok = compile_scripts()
    print()
    if not files_ok or not scripts_ok:
        print("Fix the missing project files or script errors before chatting.")
        return 1

    launcher = python_launcher()
    print("Useful checks:")
    print(f"  {launcher} -m unittest discover -s tests -v")
    print(f"  {launcher} scripts/athena_chat.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check whether the local machine is ready for ATHENA milestone 1."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


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


def check_ollama_api() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
            if response.status == 200:
                print("[ok] Ollama API is responding")
                return True
    except (OSError, urllib.error.URLError):
        pass

    print("[info] Ollama API is not responding yet. Open Ollama, then try again.")
    return False


def main() -> int:
    print("ATHENA local readiness check")
    print()

    machine = platform.machine()
    print(f"[info] CPU architecture: {machine}")
    if machine != "arm64":
        print("[warn] This guide is tuned for Apple Silicon Macs.")

    print(f"[info] Python: {sys.version.split()[0]}")
    print()

    python_ok = check_command("Python 3", ["python3", "--version"], required=True)
    check_command("Homebrew", ["brew", "--version"], required=False)
    ollama_ok = check_command("Ollama", ["ollama", "--version"], required=False)
    check_command("Docker", ["docker", "--version"], required=False)

    print()
    if ollama_ok:
        check_ollama_api()

    print()
    if not python_ok:
        print("Install Python 3 before continuing.")
        return 1

    print("Next step: install Ollama and pull qwen2.5:1.5b.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

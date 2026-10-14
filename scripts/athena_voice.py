#!/usr/bin/env python3
"""Speak and listen through the operating system's own speech tools."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def clean_for_speech(text: str) -> str:
    without_code = re.sub(r"```.*?```", " code block omitted ", text, flags=re.S)
    without_ticks = without_code.replace("`", "")
    collapsed = " ".join(without_ticks.split())
    return collapsed[:3000]


def powershell_executable() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def speak(text: str) -> int:
    cleaned = clean_for_speech(text)
    if not cleaned:
        print("Nothing to say.")
        return 1
    if sys.platform == "darwin":
        return speak_darwin(cleaned)
    if sys.platform == "win32":
        return speak_windows(cleaned)
    return speak_unix(cleaned)


def speak_darwin(text: str) -> int:
    if shutil.which("say") is None:
        print("The macOS say command is not available.")
        return 1

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(text)
            temp_path = handle.name
        result = subprocess.run(["say", "-f", temp_path], check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Speech failed: {exc}")
        return 1
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass
    return 0 if result.returncode == 0 else 1


def speak_windows(text: str) -> int:
    powershell = powershell_executable()
    if powershell is None:
        print("PowerShell is not available, so ATHENA cannot use Windows speech.")
        return 1

    env = os.environ.copy()
    env["ATHENA_SAY_TEXT"] = text
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "Add-Type -AssemblyName System.Speech; "
        "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$speaker.Speak($env:ATHENA_SAY_TEXT)"
    )
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Speech failed: {exc}")
        return 1

    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip() or "Windows speech failed.")
        return 1
    return 0


def speak_unix(text: str) -> int:
    command = shutil.which("espeak-ng") or shutil.which("espeak")
    if command is None:
        print("No local speech command found. Install espeak-ng, or use text chat.")
        return 1
    try:
        result = subprocess.run([command, text], check=False, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Speech failed: {exc}")
        return 1
    return 0 if result.returncode == 0 else 1


def listen() -> int:
    if sys.platform == "win32":
        return listen_windows()

    print(
        "Push-to-talk uses the Windows speech recognizer. "
        "On this system, type your message. /speak on can still read replies aloud when a local voice is installed."
    )
    return 1


def listen_windows() -> int:
    powershell = powershell_executable()
    if powershell is None:
        print("PowerShell is not available, so ATHENA cannot listen.", file=sys.stderr)
        return 1

    script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$engine.SetInputToDefaultAudioDevice()
$engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(8)
$engine.BabbleTimeout = [TimeSpan]::FromSeconds(6)
$engine.EndSilenceTimeout = [TimeSpan]::FromSeconds(1)
$result = $engine.Recognize()
if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) { exit 2 }
Write-Output $result.Text
"""
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".ps1", delete=False) as handle:
            handle.write(script)
            temp_path = handle.name
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", temp_path],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("Listening timed out.", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Listening failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass

    if result.returncode == 0 and result.stdout.strip():
        print(result.stdout.strip())
        return 0

    detail = result.stderr.strip() or result.stdout.strip() or "No speech recognized."
    print(detail, file=sys.stderr)
    return result.returncode or 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Speak or listen with the operating system.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    speak_parser = subparsers.add_parser("speak", help="Read text aloud. Text is read from stdin.")
    speak_parser.add_argument("text", nargs="*")
    subparsers.add_parser("listen", help="Listen once and print the recognized text.")
    args = parser.parse_args()

    if args.command == "speak":
        text = " ".join(args.text).strip() or sys.stdin.read()
        return speak(text)

    return listen()


if __name__ == "__main__":
    raise SystemExit(main())

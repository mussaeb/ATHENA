#!/usr/bin/env python3
"""Turn a short allowlisted plan into approved tool steps."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from athena_common import PROJECT_ROOT, append_safety_log, clip


PLAN_DIR = PROJECT_ROOT / "logs" / "plans"
LINE_RE = re.compile(r"^\s*(\d+)[.)]\s*([a-z_]+)\s*(?::\s*(.*))?$")
ALLOWED_VERBS = {
    "search_docs": "Search local documents. Args: query.",
    "web_search": "Search the web. Args: query.",
    "recall_history": "Search saved chats. Args: query.",
    "read_file": "Read one project file. Args: relative path.",
    "list_files": "List project files. Args: optional query.",
    "git_status": "Show git status. No args.",
    "git_diff": "Show git diff summary. No args.",
    "git_log": "Show recent commits. No args.",
    "infra_status": "Read-only infrastructure status. Args: optional docker, kubernetes, jenkins, or openstack.",
    "run_tests": "Run the ATHENA unit tests. No args.",
}
NO_ARG_VERBS = {"git_status", "git_diff", "git_log", "run_tests"}


def plan_prompt(goal: str) -> str:
    verbs = "\n".join(f"- {name}: {description}" for name, description in ALLOWED_VERBS.items())
    return (
        "Break the task into a short plan. Output only steps, one per line, in this shape:\n"
        "1. verb: arguments\n"
        "Use only the allowed verbs. Do not use shell commands, file writes, or any other verb.\n"
        "Example:\n"
        "1. read_file: README.md\n"
        "2. git_status\n\n"
        f"Allowed verbs:\n{verbs}\n\n"
        f"Task: {goal}"
    )


def parse_plan(goal: str, model_text: str) -> dict:
    steps = []
    rejected = []
    for line in model_text.splitlines():
        match = LINE_RE.match(line.strip())
        if not match:
            continue
        number = int(match.group(1))
        verb = match.group(2)
        args = (match.group(3) or "").strip()
        if verb not in ALLOWED_VERBS:
            rejected.append(
                {
                    "number": number,
                    "verb": verb,
                    "args": args,
                    "status": "rejected",
                    "output": "Verb is not allowed.",
                }
            )
            continue
        if verb in NO_ARG_VERBS:
            args = ""
        steps.append({"number": number, "verb": verb, "args": args, "status": "pending", "output": ""})

    return {
        "goal": goal,
        "created": datetime.now().isoformat(timespec="seconds"),
        "steps": steps,
        "rejected": rejected,
    }


def format_plan(plan: dict) -> str:
    lines = [f"Goal: {plan.get('goal', '')}"]
    steps = plan.get("steps", [])
    rejected = plan.get("rejected", [])
    if not steps and not rejected:
        lines.append("No executable steps found.")
    for step in steps:
        args = f": {step['args']}" if step.get("args") else ""
        lines.append(f"{step['number']}. [{step['status']}] {step['verb']}{args}")
    for step in rejected:
        lines.append(f"{step['number']}. [rejected] {step['verb']}: {step.get('args', '')} ({step.get('output', '')})")
    if any(step["status"] == "pending" for step in steps):
        lines.append("Next: /approve runs one pending step. /reject skips it.")
    return "\n".join(lines)


def format_tools() -> str:
    return "\n".join(f"- {name}: {description}" for name, description in ALLOWED_VERBS.items())


def save_plan(plan: dict, plan_dir: Path = PLAN_DIR) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan, indent=2, ensure_ascii=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (plan_dir / f"plan-{stamp}.json").write_text(payload, encoding="utf-8")
    current = plan_dir / "current.json"
    current.write_text(payload, encoding="utf-8")
    return current


def load_current_plan(plan_dir: Path = PLAN_DIR) -> dict | None:
    current = plan_dir / "current.json"
    if not current.is_file():
        return None
    return json.loads(current.read_text(encoding="utf-8"))


def next_pending(plan: dict) -> dict | None:
    return next((step for step in plan.get("steps", []) if step.get("status") == "pending"), None)


def approve_next(plan: dict, runner, log_root: Path | None = None) -> tuple[str, dict]:
    step = next_pending(plan)
    if step is None:
        return "No pending steps.", plan
    if step.get("verb") not in ALLOWED_VERBS:
        step["status"] = "rejected"
        step["output"] = "Verb is not allowed."
        append_safety_log("approve", f"{step.get('verb')} {step.get('args', '')}", approved=False, root=log_root)
        return f"Rejected unlisted verb {step.get('verb')}.", plan

    try:
        code, output = runner(step["verb"], step.get("args", ""))
    except Exception as exc:  # noqa: BLE001 - show the tool failure and keep the plan.
        code, output = 1, str(exc)

    output = clip(str(output), 8000)
    step["status"] = "done" if code == 0 else "error"
    step["output"] = output
    append_safety_log(
        "approve",
        f"{step['verb']} {step.get('args', '')}\nexit={code}\n{output}",
        approved=True,
        root=log_root,
    )
    header = f"Step {step['number']} {step['verb']} finished with status {step['status']}."
    return f"{header}\n{output}", plan


def reject_next(plan: dict, log_root: Path | None = None) -> tuple[str, dict]:
    step = next_pending(plan)
    if step is None:
        return "No pending steps.", plan
    step["status"] = "rejected"
    step["output"] = "Rejected by the user."
    append_safety_log("reject", f"{step['verb']} {step.get('args', '')}", approved=False, root=log_root)
    return f"Rejected step {step['number']}: {step['verb']}", plan


def default_runner(verb: str, args: str) -> tuple[int, str]:
    scripts = PROJECT_ROOT / "scripts"

    def run(script: str, script_args: list[str], timeout: int = 60) -> tuple[int, str]:
        try:
            result = subprocess.run(
                [sys.executable, str(scripts / script), *script_args],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 124, "Timed out."
        except OSError as exc:
            return 1, str(exc)
        output = result.stdout.strip()
        if result.stderr.strip():
            output = f"{output}\n{result.stderr.strip()}".strip()
        return result.returncode, output or "(no output)"

    if verb == "search_docs":
        if not args.strip():
            return 1, "search_docs needs a query."
        return run("athena_docs.py", ["search", args, "--limit", "4"], timeout=120)
    if verb == "web_search":
        if not args.strip():
            return 1, "web_search needs a query."
        return run("athena_web.py", ["search", args, "--limit", "4"], timeout=30)
    if verb == "recall_history":
        if not args.strip():
            return 1, "recall_history needs a query."
        return run("athena_history.py", ["search", args, "--limit", "5"])
    if verb == "read_file":
        if not args.strip():
            return 1, "read_file needs a path."
        return run("athena_code.py", ["read", args])
    if verb == "list_files":
        return run("athena_code.py", ["files", args] if args.strip() else ["files"])
    if verb == "git_status":
        return run("athena_code.py", ["git-status"])
    if verb == "git_diff":
        return run("athena_code.py", ["git-diff"])
    if verb == "git_log":
        return run("athena_code.py", ["git-log"])
    if verb == "run_tests":
        return run("athena_code.py", ["test"], timeout=180)
    if verb == "infra_status":
        choice = args.strip().lower()
        mapping = {
            "": "status",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "k8s": "kubernetes",
            "jenkins": "jenkins",
            "openstack": "openstack",
        }
        if choice not in mapping:
            return 1, "infra_status accepts docker, kubernetes, jenkins, or openstack."
        return run("athena_infra.py", [mapping[choice]], timeout=30)
    return 1, f"Verb is not allowed: {verb}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show or advance the current ATHENA plan.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("show")
    subparsers.add_parser("tools")
    subparsers.add_parser("approve")
    subparsers.add_parser("reject")
    args = parser.parse_args()

    if args.command == "tools":
        print(format_tools())
        return 0

    plan = load_current_plan()
    if plan is None:
        print("No plan yet.")
        return 1
    if args.command == "show":
        print(format_plan(plan))
        return 0
    if args.command == "approve":
        message, updated = approve_next(plan, default_runner)
    else:
        message, updated = reject_next(plan)
    save_plan(updated)
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

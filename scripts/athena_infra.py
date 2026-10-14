#!/usr/bin/env python3
"""Read-only checks for local infrastructure tools."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from athena_common import load_dotenv, redact_secrets


load_dotenv()


def clip_lines(text: str, limit: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    extra = len(lines) - limit
    return "\n".join(lines[:limit] + [f"... {extra} more lines"])


def run_command(command: list[str], timeout: int = 12) -> str:
    if shutil.which(command[0]) is None:
        return f"{command[0]} is not installed or not on PATH."

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"{command[0]} timed out after {timeout} seconds."
    except OSError as exc:
        return f"{command[0]} could not be started: {exc}"

    output = result.stdout.strip()
    error = redact_secrets(result.stderr.strip())
    if result.returncode != 0:
        return error or output or f"{command[0]} exited {result.returncode}"
    return clip_lines(output or "(no output)")


def docker_status() -> str:
    return run_command(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"])


def kubernetes_status() -> str:
    return run_command(["kubectl", "get", "pods", "-A", "--request-timeout=8s"])


def openstack_status() -> str:
    if shutil.which("openstack") is None:
        return "openstack is not installed or not on PATH."
    return run_command(["openstack", "server", "list", "--limit", "20"], timeout=20)


def jenkins_status(url: str | None = None) -> str:
    if url is None:
        raw_url = os.environ.get("ATHENA_JENKINS_URL", "").strip().rstrip("/")
    else:
        raw_url = url.strip().rstrip("/")
    if not raw_url:
        return "Jenkins URL is not set. Export ATHENA_JENKINS_URL for read-only job status."

    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "ATHENA_JENKINS_URL must be an http or https URL."

    endpoint = raw_url + "/api/json?tree=jobs[name,color]"
    request = urllib.request.Request(endpoint, headers={"User-Agent": "ATHENA-local/1.0"})
    user = os.environ.get("ATHENA_JENKINS_USER", "")
    token = os.environ.get("ATHENA_JENKINS_TOKEN", "")
    if user or token:
        basic = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {basic}")

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read(500_000).decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return f"Jenkins request failed: {redact_secrets(str(exc))}"

    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list) or not jobs:
        return "Jenkins responded with no jobs."

    lines = []
    for job in jobs[:30]:
        if not isinstance(job, dict):
            continue
        lines.append(f"- {job.get('name', 'unnamed')}: {job.get('color', 'unknown')}")
    return "\n".join(lines) or "Jenkins responded with no jobs."


def status_report() -> str:
    sections = [
        ("Docker", docker_status()),
        ("Kubernetes", kubernetes_status()),
        ("Jenkins", jenkins_status()),
        ("OpenStack", openstack_status()),
    ]
    return "\n\n".join(f"{title}\n{body}" for title, body in sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only infrastructure status for ATHENA.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("docker")
    subparsers.add_parser("kubernetes")
    subparsers.add_parser("jenkins")
    subparsers.add_parser("openstack")
    args = parser.parse_args()

    reports = {
        "status": status_report,
        "docker": docker_status,
        "kubernetes": kubernetes_status,
        "jenkins": jenkins_status,
        "openstack": openstack_status,
    }
    print(reports[args.command]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

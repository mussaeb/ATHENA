import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import athena_agent


class AgentTests(unittest.TestCase):
    def test_plan_keeps_allowlisted_steps_and_rejects_shell(self) -> None:
        plan = athena_agent.parse_plan(
            "inspect the repo",
            "1. read_file: README.md\n2. git_status: extra\n9. shell: rm -rf /\n",
        )
        self.assertEqual(plan["steps"][0]["args"], "README.md")
        self.assertEqual(plan["steps"][1]["verb"], "git_status")
        self.assertEqual(plan["steps"][1]["args"], "")
        self.assertEqual(plan["rejected"][0]["verb"], "shell")
        self.assertIn("read_file", athena_agent.plan_prompt("inspect"))
        self.assertIn("Do not use shell", athena_agent.plan_prompt("inspect"))

    def test_approve_runs_one_step_and_records_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = athena_agent.parse_plan("check", "1. git_status\n2. web_search: python release\n")
            calls = []

            def runner(verb: str, args: str) -> tuple[int, str]:
                calls.append((verb, args))
                return 0, "status ok"

            message, updated = athena_agent.approve_next(plan, runner, log_root=root)
            self.assertEqual(calls, [("git_status", "")])
            self.assertEqual(updated["steps"][0]["status"], "done")
            self.assertEqual(updated["steps"][1]["status"], "pending")
            self.assertIn("status ok", message)
            safety = (root / "logs" / "safety" / "safety.jsonl").read_text(encoding="utf-8")
            self.assertIn("git_status", safety)

            reject_message, rejected = athena_agent.reject_next(updated, log_root=root)
            self.assertEqual(rejected["steps"][1]["status"], "rejected")
            self.assertIn("Rejected", reject_message)

    def test_runner_refuses_unlisted_verbs(self) -> None:
        code, output = athena_agent.default_runner("shell", "rm -rf /")
        self.assertEqual(code, 1)
        self.assertIn("not allowed", output)

    def test_runner_refuses_to_read_outside_the_project(self) -> None:
        code, output = athena_agent.default_runner("read_file", "../.env")
        self.assertNotEqual(code, 0)
        self.assertNotIn("TOKEN", output)


if __name__ == "__main__":
    unittest.main()

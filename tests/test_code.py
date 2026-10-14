import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import athena_code
from athena_common import PROJECT_ROOT


class CodeTests(unittest.TestCase):
    def test_refuses_secrets_and_paths_outside_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
            with self.assertRaises(ValueError):
                athena_code.read_project_file(root, ".env")
            with self.assertRaises(ValueError):
                athena_code.resolve_inside(root, "../outside.txt")

    def test_snippet_must_match_once(self) -> None:
        updated = athena_code.build_updated_text("alpha beta gamma\n", "beta", "ATHENA")
        self.assertEqual(updated, "alpha ATHENA gamma\n")
        with self.assertRaises(ValueError):
            athena_code.build_updated_text("beta beta\n", "beta", "ATHENA")

    def test_parse_uses_the_last_complete_block(self) -> None:
        draft = (
            "<<<REPLACE>>>\nexample\n<<<WITH>>>\nexample\n<<<END>>>\n"
            "<<<REPLACE>>>\nbeta\n<<<WITH>>>\nATHENA\n<<<END>>>\n"
        )
        self.assertEqual(athena_code.parse_replacement(draft), ("beta", "ATHENA"))

    def test_apply_writes_only_inside_an_allowed_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "docs" / "note.md"
            target.parent.mkdir()
            target.write_text("alpha beta gamma\n", encoding="utf-8")
            updated = athena_code.build_updated_text("alpha beta gamma\n", "beta", "ATHENA")
            proposal = {
                "path": "docs/note.md",
                "original": "alpha beta gamma\n",
                "updated": updated,
                "diff": "diff",
            }
            message = athena_code.apply_proposal(root, proposal)
            self.assertIn("docs/note.md", message)
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha ATHENA gamma\n")

            target.write_text("changed since the proposal\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                athena_code.apply_proposal(root, proposal)
            with self.assertRaises(ValueError):
                athena_code.apply_proposal(root, {"path": ".env", "original": "", "updated": "nope\n", "diff": ""})

    def test_list_files_can_see_the_chat_script(self) -> None:
        listing = athena_code.list_project_files(PROJECT_ROOT, "athena_chat")
        self.assertIn("scripts/athena_chat.py", listing.replace("\\", "/"))

    def test_test_command_uses_this_interpreter(self) -> None:
        command = athena_code.test_command(PROJECT_ROOT)
        self.assertIn("unittest", command)
        self.assertTrue(command[0])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import athena_history


class HistoryTests(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(athena_history.slugify("Project Work"), "project-work")
        self.assertEqual(athena_history.slugify("   "), "chat")

    def test_search_and_list_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            entry = {
                "timestamp": "2026-10-14T12:00:00",
                "role": "user",
                "session": "lab",
                "content": "We discussed the OpenStack cluster.",
            }
            (log_dir / "athena-20261014-120000-lab.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
            found = athena_history.search_chats("OpenStack cluster", log_dir=log_dir)
            listing = athena_history.list_sessions(log_dir)

        self.assertIn("OpenStack", found)
        self.assertIn("[lab]", listing)
        self.assertIn("discussed", listing)


if __name__ == "__main__":
    unittest.main()

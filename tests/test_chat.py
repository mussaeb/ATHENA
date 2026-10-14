import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import athena_chat


class ChatTests(unittest.TestCase):
    def test_help_commands_are_recognized(self) -> None:
        commands = set(re.findall(r"(?<!\S)(/[a-z0-9]+)", athena_chat.help_text()))
        self.assertTrue(commands)
        self.assertTrue(commands <= athena_chat.COMMAND_NAMES)
        self.assertTrue(athena_chat.is_known_command("/docmode on"))
        self.assertFalse(athena_chat.is_known_command("/indexes"))

    def test_handlers_cover_every_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = athena_chat.ChatSession(log_dir=Path(directory))
            self.assertEqual(set(session.command_handlers()), athena_chat.COMMAND_NAMES)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(session.handle("/help"), "continue")
                self.assertEqual(session.handle("/not-a-command"), "continue")
                self.assertEqual(session.handle("/docmode on"), "continue")
                self.assertEqual(session.handle("/webmode"), "continue")
                self.assertEqual(session.handle("/name Project Work"), "continue")
            self.assertTrue(session.docmode)
            self.assertFalse(session.webmode)
            self.assertIn("Document mode is on", output.getvalue())
            self.assertIn("Web mode is off", output.getvalue())
            files = list(Path(directory).glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        self.assertIn("project-work", files[0].name)

    def test_grounded_message_names_only_the_tools_that_ran(self) -> None:
        text = athena_chat.build_grounded_message("What can ATHENA do?", docs_context="overview")
        self.assertEqual(text.count("What can ATHENA do?"), 1)
        self.assertIn("Local document search results:", text)
        self.assertNotIn("Web search results:", text)

    def test_model_window_keeps_system_messages_and_recent_turns(self) -> None:
        messages = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
        ]
        kept = athena_chat.model_messages(messages, limit=2)
        self.assertEqual([item["content"] for item in kept], ["s", "2", "3"])
        self.assertEqual([item["content"] for item in athena_chat.model_messages(messages, limit=0)], ["s"])

    def test_secret_memory_warning(self) -> None:
        self.assertIsNotNone(athena_chat.secret_memory_warning("The api key is abc"))
        self.assertIsNone(athena_chat.secret_memory_warning("Prefer a small context window"))

    def test_default_prompt_forbids_fake_searches(self) -> None:
        prompt = athena_chat.DEFAULT_SYSTEM_PROMPT
        self.assertIn("Web search results:", prompt)
        self.assertIn("Never claim", prompt)


if __name__ == "__main__":
    unittest.main()

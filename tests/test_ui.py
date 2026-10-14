import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import _path  # noqa: F401
import athena_chat
import athena_ui


class FakeSession:
    def __init__(self) -> None:
        self.speak = False
        self.docmode = False
        self.webmode = False
        self.session_name = "chat"
        self.calls: list[str] = []

    def exchange(self, user_text: str, *, defer_speech: bool = False) -> dict:
        self.calls.append(user_text)
        self.last_defer = defer_speech
        return {
            "text": f"echo {user_text}",
            "exit": False,
            "speak": self.speak,
            "docmode": self.docmode,
            "webmode": self.webmode,
            "session": self.session_name,
            "model": "test-model",
        }


class InterfaceTests(unittest.TestCase):
    def test_page_offers_voice_sources_and_code_review(self) -> None:
        page = athena_ui.PAGE_PATH.read_text(encoding="utf-8")
        self.assertIn("webkitSpeechRecognition", page)
        self.assertIn("Speak replies", page)
        self.assertIn("Documents", page)
        self.assertIn("Web", page)
        self.assertIn("Save", page)
        self.assertIn("Hide", page)
        self.assertIn("New file", page)
        self.assertIn("Find in file", page)
        self.assertIn("Apply", page)
        self.assertIn("__ATHENA_TOKEN__", page)
        self.assertIn("Ask", page)
        self.assertIn("Open project", page)
        self.assertIn("sends audio to Google", page)

    def test_voice_reply_is_only_for_conversation(self) -> None:
        self.assertTrue(athena_ui.wants_voice_reply("What time is it?", True))
        self.assertTrue(athena_ui.wants_voice_reply("/askweb latest Python", True))
        self.assertFalse(athena_ui.wants_voice_reply("/git", True))
        self.assertFalse(athena_ui.wants_voice_reply("hello", False))

    def test_local_page_round_trip(self) -> None:
        session = FakeSession()
        spoken: list[str] = []
        original = athena_ui.speak_later
        athena_ui.speak_later = spoken.append
        server = athena_ui.AthenaServer(("127.0.0.1", 0), athena_ui.build_handler(session))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("Listen", html)
            self.assertIn("test-token", html)
            self.assertNotIn("__ATHENA_TOKEN__", html)

            blocked = urllib.request.Request(
                base + "/api/terminal",
                data=b'{"command":"cd scripts"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as missing_token:
                urllib.request.urlopen(blocked, timeout=5)
            self.assertEqual(missing_token.exception.code, 403)
            missing_token.exception.close()

            self._post(base + "/api/settings", {"speak": True, "docmode": True, "webmode": True})
            self.assertTrue(session.speak)
            self.assertTrue(session.docmode)
            self.assertTrue(session.webmode)

            payload = self._post(base + "/api/turn", {"text": "How does indexing work?"})
            self.assertEqual(payload["text"], "echo How does indexing work?")
            self.assertTrue(payload["voiced"])
            self.assertEqual(spoken, ["echo How does indexing work?"])
            self.assertTrue(session.last_defer)

            quiet = self._post(base + "/api/turn", {"text": "/git"})
            self.assertFalse(quiet["voiced"])
            self.assertEqual(len(spoken), 1)

            with self.assertRaises(urllib.error.HTTPError) as rejected:
                self._post(base + "/api/code/file", {})
            self.assertEqual(rejected.exception.code, 400)
            rejected.exception.close()

            with urllib.request.urlopen(base + "/api/code/file?path=README.md", timeout=5) as response:
                readme = json.load(response)
            self.assertIn("ATHENA", readme["text"])

            with urllib.request.urlopen(base + "/api/code/tree?path=scripts", timeout=5) as response:
                tree = json.load(response)
            names = [item["name"] for item in tree["entries"]]
            self.assertIn("athena_ui.py", names)
            self.assertEqual(tree["path"], "scripts")

            request = urllib.request.Request(
                base + "/api/turn",
                data=b'{"text":"' + (b"a" * 65000) + b'"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as too_big:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(too_big.exception.code, 400)
            too_big.exception.close()
        finally:
            athena_ui.speak_later = original
            server.shutdown()
            server.server_close()

    def test_real_session_can_change_modes_without_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = athena_chat.ChatSession(log_dir=Path(directory))
            server = athena_ui.AthenaServer(("127.0.0.1", 0), athena_ui.build_handler(session))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                payload = self._post(base + "/api/turn", {"text": "/webmode on"})
                self.assertIn("Web mode is on", payload["text"])
                self.assertTrue(session.webmode)
                self.assertFalse(payload["voiced"])
            finally:
                server.shutdown()
                server.server_close()

    def test_folder_listing_stays_inside_the_project(self) -> None:
        listing = athena_ui.list_directory(athena_ui.PROJECT_ROOT, "")
        names = [item["name"] for item in listing["entries"]]
        self.assertIn("scripts", names)
        self.assertNotIn(".git", names)
        with self.assertRaises(ValueError):
            athena_ui.list_directory(athena_ui.PROJECT_ROOT, "..")

    def test_project_draft_stays_inside_the_selected_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "docs" / "note.md"
            note.parent.mkdir()
            note.write_text("hello\n", encoding="utf-8")
            (root / "README.md").write_text("root\n", encoding="utf-8")
            proposals = root / "proposals"
            drafted = (
                "I would change the note.\n"
                "<<<PATH>>>\n"
                "docs/note.md\n"
                "<<<REPLACE>>>\n"
                "hello\n"
                "<<<WITH>>>\n"
                "hello there\n"
                "<<<END>>>\n"
            )
            proposal = athena_ui.proposal_from_model_text(root, drafted, "docs", proposals)
            self.assertEqual(proposal["path"], "docs/note.md")
            self.assertIn("hello there", proposal["diff"])
            outside = drafted.replace("docs/note.md", "README.md").replace("hello", "root", 1)
            with self.assertRaises(ValueError):
                athena_ui.proposal_from_model_text(root, outside, "docs", proposals)
            escaped = drafted.replace("docs/note.md", "docs/../README.md")
            with self.assertRaises(ValueError):
                athena_ui.proposal_from_model_text(root, escaped, "docs", proposals)

    def test_code_view_can_open_another_project(self) -> None:
        session = FakeSession()
        server = athena_ui.AthenaServer(("127.0.0.1", 0), athena_ui.build_handler(session))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/api/code/places", timeout=5) as response:
                places = json.load(response)
            self.assertTrue(any(item["name"] == "Home" for item in places["entries"]))

            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "src").mkdir()
                (root / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")
                opened = self._post(base + "/api/workspace", {"path": str(root)})
                self.assertEqual(opened["path"], str(root.resolve()))
                with urllib.request.urlopen(base + "/api/code/tree", timeout=5) as response:
                    tree = json.load(response)
                self.assertIn("src", [item["name"] for item in tree["entries"]])
                with urllib.request.urlopen(base + "/api/code/file?path=src/app.py", timeout=5) as response:
                    opened_file = json.load(response)
                self.assertIn("print(1)", opened_file["text"])
        finally:
            server.shutdown()
            server.server_close()

    def test_apply_stays_inside_the_opened_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "notes.txt"
            note.write_text("hello\n", encoding="utf-8")
            drafted = (
                "Change the note.\n"
                "<<<PATH>>>\n"
                "notes.txt\n"
                "<<<REPLACE>>>\n"
                "hello\n"
                "<<<WITH>>>\n"
                "hello there\n"
                "<<<END>>>\n"
            )
            proposals = root / "proposals"
            proposal = athena_ui.proposal_from_model_text(root, drafted, "", proposals)
            self.assertEqual(proposal["path"], "notes.txt")
            workspace = athena_ui.Workspace(root)
            workspace.proposal_dir = proposals
            message = athena_ui.apply_workspace_proposal(workspace)
            self.assertIn("notes.txt", message)
            self.assertEqual(note.read_text(encoding="utf-8"), "hello there\n")
            with tempfile.TemporaryDirectory() as other:
                workspace.open(Path(other))
                with self.assertRaises(ValueError):
                    athena_ui.apply_workspace_proposal(workspace)

    def test_editor_save_writes_only_the_open_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "notes.txt"
            note.write_text("hello\n", encoding="utf-8")
            secret = root / ".env"
            secret.write_text("TOKEN=1\n", encoding="utf-8")
            session = FakeSession()
            server = athena_ui.AthenaServer(
                ("127.0.0.1", 0),
                athena_ui.build_handler(session, workspace=athena_ui.Workspace(root)),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urllib.request.urlopen(base + "/api/code/file?path=notes.txt", timeout=5) as response:
                    opened = json.load(response)
                self.assertEqual(opened["text"], "hello\n")
                saved = self._post(base + "/api/code/file", {"path": "notes.txt", "text": "changed\n"})
                self.assertIn("Saved", saved["text"])
                self.assertEqual(note.read_text(encoding="utf-8"), "changed\n")
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    self._post(base + "/api/code/file", {"path": ".env", "text": "no\n"})
                self.assertEqual(rejected.exception.code, 400)
                rejected.exception.close()
                self.assertEqual(secret.read_text(encoding="utf-8"), "TOKEN=1\n")
                created = self._post(base + "/api/code/file", {"path": "src/new.txt", "text": "fresh\n", "create": True})
                self.assertIn("Saved", created["text"])
                self.assertEqual((root / "src" / "new.txt").read_text(encoding="utf-8"), "fresh\n")
                with self.assertRaises(urllib.error.HTTPError) as exists:
                    self._post(base + "/api/code/file", {"path": "notes.txt", "text": "again\n", "create": True})
                self.assertEqual(exists.exception.code, 400)
                exists.exception.close()
                self.assertEqual(note.read_text(encoding="utf-8"), "changed\n")
            finally:
                server.shutdown()
                server.server_close()

    def test_project_picker_refuses_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory) / "notes.txt"
            note.write_text("x\n", encoding="utf-8")
            ssh = Path(directory) / ".ssh"
            ssh.mkdir()
            with self.assertRaises(ValueError):
                athena_ui.open_project_folder(str(note))
            with self.assertRaises(ValueError):
                athena_ui.open_project_folder(str(ssh))

    def test_terminal_cannot_leave_the_project(self) -> None:
        terminal = athena_ui.ProjectTerminal(athena_ui.PROJECT_ROOT)
        self.assertEqual(terminal.run("cd scripts")["cwd"], "scripts")
        self.assertEqual(terminal.run("cd ..")["cwd"], ".")
        with self.assertRaises(ValueError):
            terminal.run("cd ..")
        command = "Write-Output athena-terminal-ok" if os.name == "nt" else "printf athena-terminal-ok"
        result = terminal.run(command)
        self.assertEqual(result["code"], 0)
        self.assertIn("athena-terminal-ok", result["text"])

    def _post(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Athena-Token": "test-token"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)


if __name__ == "__main__":
    unittest.main()

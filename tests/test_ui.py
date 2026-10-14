import json
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
        self.assertIn("Draft change", page)
        self.assertIn("Apply", page)
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
            self.assertEqual(rejected.exception.code, 404)
            rejected.exception.close()

            with urllib.request.urlopen(base + "/api/code/file?path=README.md", timeout=5) as response:
                readme = json.load(response)
            self.assertIn("ATHENA", readme["text"])

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

    def _post(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)


if __name__ == "__main__":
    unittest.main()

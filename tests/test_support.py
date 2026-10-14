import base64
import os
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import athena_common
import athena_infra
import athena_vision
import athena_voice


class SupportTests(unittest.TestCase):
    def test_dotenv_does_not_override_existing_variables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "ATHENA_TEST_ONLY=hello\nATHENA_MODEL=from-file\n# comment\nexport ATHENA_TEST_QUOTED=\"quoted\"\n",
                encoding="utf-8",
            )
            os.environ.pop("ATHENA_TEST_ONLY", None)
            os.environ.pop("ATHENA_TEST_QUOTED", None)
            previous_model = os.environ.get("ATHENA_MODEL")
            os.environ["ATHENA_MODEL"] = "already"
            try:
                athena_common.load_dotenv(root)
                self.assertEqual(os.environ["ATHENA_TEST_ONLY"], "hello")
                self.assertEqual(os.environ["ATHENA_TEST_QUOTED"], "quoted")
                self.assertEqual(os.environ["ATHENA_MODEL"], "already")
            finally:
                os.environ.pop("ATHENA_TEST_ONLY", None)
                os.environ.pop("ATHENA_TEST_QUOTED", None)
                if previous_model is None:
                    os.environ.pop("ATHENA_MODEL", None)
                else:
                    os.environ["ATHENA_MODEL"] = previous_model

    def test_scripts_do_not_invoke_a_shell(self) -> None:
        scripts = athena_common.PROJECT_ROOT / "scripts"
        for path in scripts.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", text)
            self.assertNotIn("os.system(", text)

    def test_mac_listen_explains_when_swift_is_missing(self) -> None:
        import contextlib
        import io

        original = athena_voice.shutil.which
        athena_voice.shutil.which = lambda _name: None
        error = io.StringIO()
        try:
            with contextlib.redirect_stderr(error):
                code = athena_voice.listen_darwin()
        finally:
            athena_voice.shutil.which = original
        self.assertEqual(code, 1)
        self.assertIn("athena_ui.py", error.getvalue())
        self.assertTrue((athena_common.PROJECT_ROOT / "scripts" / "athena_listen_mac.swift").is_file())

    def test_speech_cleanup_drops_code_blocks(self) -> None:
        spoken = athena_voice.clean_for_speech("Before ```print('secret')``` after")
        self.assertNotIn("secret", spoken)
        self.assertIn("code block omitted", spoken)

    def test_vision_stays_off_without_a_model_and_rejects_bad_files(self) -> None:
        message = athena_vision.describe_image(Path("missing.png"), "What is this?", model="")
        self.assertIn("ATHENA_VISION_MODEL", message)
        payload = athena_vision.build_payload("moondream", "What is this?", b"png")
        self.assertEqual(payload["model"], "moondream")
        self.assertEqual(payload["messages"][0]["images"], [base64.b64encode(b"png").decode("ascii")])
        with tempfile.TemporaryDirectory() as directory:
            notes = Path(directory) / "notes.txt"
            notes.write_text("hello", encoding="utf-8")
            with self.assertRaises(ValueError):
                athena_vision.validate_image(notes)

    def test_infra_reports_missing_tools_without_calling_them(self) -> None:
        self.assertIn("not installed", athena_infra.run_command(["athena-missing-binary-xyz"]))
        self.assertIn("not set", athena_infra.jenkins_status(""))
        self.assertIn("http or https", athena_infra.jenkins_status("ftp://jenkins.local"))

    def test_redacts_urls_with_passwords(self) -> None:
        self.assertNotIn("secret", athena_common.redact_secrets("https://user:secret@jenkins.local/job"))


if __name__ == "__main__":
    unittest.main()

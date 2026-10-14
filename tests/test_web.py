import unittest

import _path  # noqa: F401
import athena_web


class WebTests(unittest.TestCase):
    def test_decode_duckduckgo_redirect(self) -> None:
        href = "https://lite.duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fathena&rut=1"
        self.assertEqual(athena_web.decode_result_url(href), "https://example.com/athena")
        self.assertIsNone(athena_web.decode_result_url("https://duckduckgo.com/y.js?ad=1"))

    def test_parse_lite_results(self) -> None:
        html = """
        <html><body>
          <a href="https://duckduckgo.com/y.js?ad=1">Ignore ads</a>
          <a href="https://lite.duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fathena&rut=1">ATHENA project</a>
          <td class="result-snippet">Local assistant for engineering.</td>
        </body></html>
        """
        results = athena_web.parse_duckduckgo_lite(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://example.com/athena")
        self.assertEqual(results[0]["title"], "ATHENA project")
        self.assertIn("engineering", results[0]["snippet"])

    def test_format_includes_source_url(self) -> None:
        text = athena_web.format_web_results(
            [{"title": "Example", "url": "https://example.com/athena", "snippet": "Local assistant", "source": "wikipedia"}]
        )
        self.assertIn("https://example.com/athena", text)
        self.assertIn("source: wikipedia", text)

    def test_blocks_unlisted_hosts(self) -> None:
        with self.assertRaises(RuntimeError):
            athena_web.fetch_url("https://example.com/search")
        with self.assertRaises(RuntimeError):
            athena_web.fetch_url("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()

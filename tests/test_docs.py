import tempfile
import unittest
import zipfile
from pathlib import Path

import _path  # noqa: F401
import athena_docs


class DocsTests(unittest.TestCase):
    def test_chunk_text_advances(self) -> None:
        chunks = athena_docs.chunk_text("word " * 500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunks))

    def test_docx_keeps_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.docx"
            xml = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Alpha project</w:t></w:r></w:p>
    <w:p><w:r><w:t>Beta notes</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            text = athena_docs.read_docx(path)

        self.assertIn("Alpha project", text)
        self.assertIn("Beta notes", text)

    def test_xlsx_does_not_treat_numbers_as_shared_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sheet.xlsx"
            shared = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>secretword</t></si>
</sst>
"""
            sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row>
      <c t="s"><v>0</v></c>
      <c><v>0</v></c>
      <c t="inlineStr"><is><t>inlinevalue</t></is></c>
    </row>
  </sheetData>
</worksheet>
"""
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/sharedStrings.xml", shared)
                archive.writestr("xl/worksheets/sheet1.xml", sheet)
            text = athena_docs.read_xlsx(path)

        self.assertEqual(text.splitlines(), ["secretword", "0", "inlinevalue"])

    def test_index_skips_hidden_directories_and_searches_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes"
            source.mkdir()
            hidden = source / ".git"
            hidden.mkdir()
            (hidden / "secret.md").write_text("token secretvalue", encoding="utf-8")
            (source / "story.md").write_text("ATHENA remembers the Kubernetes platform team.", encoding="utf-8")
            index = athena_docs.build_index(source_dirs=[source], index_file=root / "index.json")

        blob = "\n".join(item["text"] for item in index["documents"])
        self.assertIn("Kubernetes", blob)
        self.assertNotIn("secretvalue", blob)
        results = athena_docs.search_documents(index["documents"], "Kubernetes platform")
        self.assertTrue(results)
        self.assertIn("Kubernetes", results[0]["text"])


if __name__ == "__main__":
    unittest.main()

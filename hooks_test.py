"""Tests for docs/hooks.py"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hooks import on_post_build


class HooksTest(unittest.TestCase):
    def test_noop_when_root_llms_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            docs = site / "docs_src"
            docs.mkdir()
            (site / "llms.txt").write_text("# already\n", encoding="utf-8")
            on_post_build({"site_dir": str(site), "docs_dir": str(docs)})
            self.assertEqual((site / "llms.txt").read_text(encoding="utf-8"), "# already\n")

    def test_copies_from_en_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            docs = site / "docs_src"
            docs.mkdir()
            (site / "en").mkdir()
            (site / "en" / "llms.txt").write_text("# from en\n", encoding="utf-8")
            on_post_build({"site_dir": str(site), "docs_dir": str(docs)})
            self.assertEqual((site / "llms.txt").read_text(encoding="utf-8"), "# from en\n")

    def test_copies_from_docs_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            docs = Path(tmp) / "docs_src"
            (docs / "en").mkdir(parents=True)
            (docs / "en" / "llms.txt").write_text("# from docs\n", encoding="utf-8")
            on_post_build({"site_dir": str(site), "docs_dir": str(docs)})
            self.assertEqual((site / "llms.txt").read_text(encoding="utf-8"), "# from docs\n")

    def test_noop_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            docs = Path(tmp) / "docs_src"
            docs.mkdir()
            on_post_build({"site_dir": str(site), "docs_dir": str(docs)})
            self.assertFalse((site / "llms.txt").exists())

    def test_copies_schemas_from_monorepo_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Mimic docs/docs as docs_dir → parent.parent/schemas
            docs = root / "docs" / "docs"
            docs.mkdir(parents=True)
            site = root / "site"
            site.mkdir()
            schemas = root / "schemas"
            schemas.mkdir()
            (schemas / "catalog.json").write_text(
                json.dumps({"operatorVersion": "1.9.0"}), encoding="utf-8"
            )
            (schemas / "dataflow.json").write_text("{}", encoding="utf-8")
            on_post_build({"site_dir": str(site), "docs_dir": str(docs)})
            self.assertTrue((site / "schemas" / "catalog.json").is_file())
            self.assertTrue((site / "schemas" / "dataflow.json").is_file())


if __name__ == "__main__":
    unittest.main()

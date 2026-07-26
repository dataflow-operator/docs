"""Tests for docs/verify_nav_files.py"""

from __future__ import annotations

import unittest

from verify_nav_files import collect_nav_paths, main


class CollectNavPathsTest(unittest.TestCase):
    def test_extracts_md_paths_from_nav_only(self) -> None:
        text = """
site_name: Test
exclude_docs: |
  **/orphan.md
nav:
  - Home: index.md
  - Tools:
      - CLI: cli.md
      - Helm Values: helm-values.md
markdown_extensions:
  - admonition
"""
        self.assertEqual(
            collect_nav_paths(text),
            {"index.md", "cli.md", "helm-values.md"},
        )

    def test_ignores_non_nav_md_mentions(self) -> None:
        text = """
hooks:
  - hooks.py
nav:
  - Getting Started: getting-started.md
"""
        self.assertEqual(collect_nav_paths(text), {"getting-started.md"})

    def test_empty_when_no_nav(self) -> None:
        self.assertEqual(collect_nav_paths("site_name: x\n"), set())


class VerifyNavMainTest(unittest.TestCase):
    def test_main_ok_for_real_mkdocs(self) -> None:
        # Runs against the live docs/mkdocs.yml + en/ru trees.
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()

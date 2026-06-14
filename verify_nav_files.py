#!/usr/bin/env python3
"""Fail if nav-referenced markdown files are missing under docs/docs/en/ and docs/docs/ru/."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def collect_nav_paths(mkdocs_text: str) -> set[str]:
    """Extract markdown paths from the nav: section only."""
    nav_match = re.search(r"^nav:\n(.*?)(?:^[a-z_]+:|\Z)", mkdocs_text, re.MULTILINE | re.DOTALL)
    if not nav_match:
        return set()
    nav_block = nav_match.group(1)
    return set(re.findall(r":\s+([a-z0-9][a-z0-9_/-]*\.md)\s*$", nav_block, re.MULTILINE))


def main() -> int:
    docs_project = Path(__file__).resolve().parent
    mkdocs_yml = docs_project / "mkdocs.yml"
    text = mkdocs_yml.read_text(encoding="utf-8")
    paths = sorted(collect_nav_paths(text))
    missing: list[str] = []
    for rel in paths:
        for locale in ("en", "ru"):
            target = docs_project / "docs" / locale / rel
            if not target.is_file():
                missing.append(f"{locale}/{rel}")
    if missing:
        print("Missing nav targets:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(f"ok: {len(paths)} nav pages × 2 locales verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

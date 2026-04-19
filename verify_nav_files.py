#!/usr/bin/env python3
"""Fail if any markdown path referenced in mkdocs.yml nav is missing under docs/docs/."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    docs_project = Path(__file__).resolve().parent
    mkdocs_yml = docs_project / "mkdocs.yml"
    text = mkdocs_yml.read_text(encoding="utf-8")
    paths = sorted(set(re.findall(r"\b(?:en|ru)/[a-z0-9_-]+\.md\b", text)))
    missing: list[str] = []
    for rel in paths:
        target = docs_project / "docs" / rel
        if not target.is_file():
            missing.append(rel)
    if missing:
        print("Missing nav targets:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1
    hub = docs_project / "docs" / "index.md"
    if not hub.is_file():
        print("Missing docs/docs/index.md", file=sys.stderr)
        return 1
    print(f"ok: {len(paths)} nav markdown files and hub index exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""MkDocs hooks for DataFlow docs site."""

from __future__ import annotations

import shutil
from pathlib import Path


def on_post_build(config, **kwargs) -> None:
    """Ensure site/llms.txt exists for LLM crawlers.

    With mkdocs-static-i18n (en = default), ``docs/en/llms.txt`` is already
    copied to the site root. This hook is a safety net if the file lands only
    under ``en/`` or needs to be copied from the docs source.
    """
    site_dir = Path(config["site_dir"])
    dest = site_dir / "llms.txt"
    if dest.is_file():
        return

    docs_dir = Path(config["docs_dir"])
    for candidate in (
        site_dir / "en" / "llms.txt",
        docs_dir / "en" / "llms.txt",
        docs_dir / "llms.txt",
    ):
        if candidate.is_file():
            shutil.copy2(candidate, dest)
            return

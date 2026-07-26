"""MkDocs hooks for DataFlow docs site."""

from __future__ import annotations

import shutil
from pathlib import Path


def on_post_build(config, **kwargs) -> None:
    """Post-build: ensure llms.txt at site root and publish schemas/."""
    site_dir = Path(config["site_dir"])
    docs_dir = Path(config["docs_dir"])
    _ensure_llms_txt(site_dir, docs_dir)
    _copy_schemas(site_dir, docs_dir)


def _ensure_llms_txt(site_dir: Path, docs_dir: Path) -> None:
    """Ensure site/llms.txt exists for LLM crawlers.

    With mkdocs-static-i18n (en = default), ``docs/en/llms.txt`` is already
    copied to the site root. This hook is a safety net if the file lands only
    under ``en/`` or needs to be copied from the docs source.
    """
    dest = site_dir / "llms.txt"
    if dest.is_file():
        return

    for candidate in (
        site_dir / "en" / "llms.txt",
        docs_dir / "en" / "llms.txt",
        docs_dir / "llms.txt",
    ):
        if candidate.is_file():
            shutil.copy2(candidate, dest)
            return


def _schemas_source(docs_dir: Path) -> Path | None:
    """Resolve monorepo schemas/ relative to MkDocs docs_dir (docs/docs)."""
    for candidate in (
        docs_dir.parent.parent / "schemas",  # docs/docs → repo/schemas
        docs_dir.parent / "schemas",  # docs → docs/schemas
        Path.cwd() / "schemas",
        Path.cwd().parent / "schemas",
    ):
        if (candidate / "catalog.json").is_file():
            return candidate
    return None


def _copy_schemas(site_dir: Path, docs_dir: Path) -> None:
    """Copy machine-readable schemas into site/schemas for stable URLs."""
    src = _schemas_source(docs_dir)
    if src is None:
        return
    dest = site_dir / "schemas"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

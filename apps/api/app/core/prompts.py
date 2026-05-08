"""Centralized loader for Claude system prompts.

Single source of truth for all system prompts used by Vintiz services.
Prompts live as Markdown files in ``apps/api/prompts/v{N}/{name}.md``
and are loaded lazily with an LRU cache.

Each prompt file is expected to have a small header followed by H2
sections (``## System``, ``## User template``, ``## Cost control``…).
By default the loader extracts the body of the ``## System`` section ;
any other section can be requested via the ``section`` argument.

Versioning : bump the version directory (``v1`` → ``v2``) when the
model or the contract changes. Old versions stay on disk so the
service can roll back without redeploying.

Usage:
    from app.core.prompts import load_prompt

    prompt = load_prompt(
        "personal_shopper",
        fallback="Tu es la Personal Shopper de Vintiz…",
    )
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# apps/api/app/core/prompts.py → parents[2] = apps/api/
_PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"


class PromptNotFoundError(LookupError):
    """Raised when a prompt file or section cannot be located on disk."""


def _extract_section(text: str, header: str) -> str:
    """Return the body of the ``## {header}`` section.

    The body ends at the next ``## `` heading (or at the end of file).
    Whitespace is stripped from both ends. Raises ``PromptNotFoundError``
    if the marker is absent.
    """
    marker = f"## {header}"
    if marker not in text:
        raise PromptNotFoundError(
            f"Section {marker!r} missing in prompt body"
        )
    after = text.split(marker, 1)[1]
    # Stop at the next H2 heading
    if "\n## " in after:
        after = after.split("\n## ", 1)[0]
    return after.strip()


@lru_cache(maxsize=64)
def load_prompt(
    name: str,
    *,
    section: str = "System",
    version: str = "v1",
    fallback: str | None = None,
) -> str:
    """Return the body of a section in a prompt file.

    Args:
        name: prompt file name without extension (e.g. ``personal_shopper``)
        section: H2 section header to extract (default ``System``)
        version: prompt version directory (default ``v1``)
        fallback: inline string returned if the file is absent. If
            ``None``, a missing file raises ``PromptNotFoundError``.

    The result is cached per ``(name, section, version)`` tuple so a
    subsequent call is free. Use :func:`reset_cache` in tests when you
    need to reload after a file change.
    """
    path = _PROMPTS_ROOT / version / f"{name}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if fallback is not None:
            return fallback
        raise PromptNotFoundError(
            f"Prompt file not found: {path}. Create it or pass `fallback`."
        ) from None
    try:
        return _extract_section(text, section)
    except PromptNotFoundError:
        # Section not found — last resort, return the whole file body
        # so callers don't crash on a malformed prompt.
        return text.strip()


def reset_cache() -> None:
    """Clear the LRU cache. Useful in tests after touching prompt files."""
    load_prompt.cache_clear()

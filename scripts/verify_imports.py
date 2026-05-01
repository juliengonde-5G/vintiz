#!/usr/bin/env python3
"""Static check for broken multi-line imports in TypeScript/JSX.

Catches the exact pattern that broke prod (Sprint 3 → Sprint 4 deploy):

    import {
    import { foo } from '...';   <-- second import injected mid-block
      a, b, c,
    } from '...';

The SWC parser rejects this with ``cannot import as reserved word``,
which only surfaces during ``npm run build`` — too late if the CI
gate isn't required for merge. This script runs in milliseconds and
fails the CI early with a clear pointer to the offending file:line.

Usage::

    python scripts/verify_imports.py apps/web/src apps/site/src

Exit code 0 = clean, 1 = broken imports found. Designed to run before
``npm run build`` in the CI workflow so the failure message is
unambiguous.
"""
from __future__ import annotations

import sys
from pathlib import Path


SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def check_file(path: Path) -> list[str]:
    """Return human-readable error messages for ``path`` (empty on clean)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    errors: list[str] = []
    lines = text.split("\n")
    in_multiline_import = False
    multiline_start_line = 0

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        if in_multiline_import:
            # Looking for the closing ``} from '...'`` of a multi-line import.
            # Any ``import`` statement inside the open block is a corruption
            # introduced by an automated rewriter that didn't notice the
            # multi-line state.
            if stripped.startswith("import "):
                errors.append(
                    f"{path}:{idx}: import statement injected inside an "
                    f"open multi-line import that started at line "
                    f"{multiline_start_line}: {stripped!r}"
                )
            if stripped.startswith("}") and "from" in stripped:
                in_multiline_import = False
            continue

        # Open a multi-line import: ``import {`` on its own line, with no
        # ``from`` on the same line (a single-line ``import { x } from '...'``
        # closes immediately and is fine).
        if stripped == "import {" or (
            stripped.startswith("import {") and "from" not in stripped
        ):
            in_multiline_import = True
            multiline_start_line = idx

    return errors


def walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in SCAN_EXTENSIONS:
            continue
        # Skip generated / vendored paths — keeps the scan fast and
        # noise-free on a clean checkout.
        parts = p.parts
        if any(seg in {"node_modules", ".next", "dist", "build"} for seg in parts):
            continue
        out.append(p)
    return out


def main(argv: list[str]) -> int:
    roots = [Path(arg) for arg in argv[1:]]
    if not roots:
        print(
            "Usage: verify_imports.py <dir> [<dir> ...]",
            file=sys.stderr,
        )
        return 2

    files: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"verify_imports: skip missing path {root}", file=sys.stderr)
            continue
        if root.is_file():
            files.append(root)
        else:
            files.extend(walk(root))

    all_errors: list[str] = []
    for f in files:
        all_errors.extend(check_file(f))

    if all_errors:
        print(
            f"verify_imports: {len(all_errors)} broken import(s) detected:",
            file=sys.stderr,
        )
        for line in all_errors:
            print(f"  {line}", file=sys.stderr)
        print(
            "Hint: see hotfix PR #49 — an automated migration likely "
            "inserted a single-line import in the middle of a multi-line "
            "`import { ... } from '...'` block.",
            file=sys.stderr,
        )
        return 1

    print(f"verify_imports: scanned {len(files)} file(s) — clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

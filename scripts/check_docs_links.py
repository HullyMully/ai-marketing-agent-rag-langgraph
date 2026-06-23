"""Validate bilingual documentation.

Checks, with no external dependencies:
- every English doc has a Russian counterpart (`*.ru.md`) and vice versa;
- each doc carries the correct language-switch line at the top.

Usage:
    python scripts/check_docs_links.py
Exits 0 when everything is consistent, otherwise prints problems and exits 1.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (english_path, russian_path) relative to repo root.
DOC_PAIRS: list[tuple[str, str]] = [
    ("README.md", "README.ru.md"),
    ("docs/architecture.md", "docs/architecture.ru.md"),
    ("docs/api.md", "docs/api.ru.md"),
    ("docs/rag.md", "docs/rag.ru.md"),
    ("docs/langgraph-flow.md", "docs/langgraph-flow.ru.md"),
    ("docs/web-demo.md", "docs/web-demo.ru.md"),
    ("docs/limitations.md", "docs/limitations.ru.md"),
    ("docs/roadmap.md", "docs/roadmap.ru.md"),
    ("docs/portfolio-case-study.md", "docs/portfolio-case-study.ru.md"),
    ("docs/demo/demo-walkthrough.md", "docs/demo/demo-walkthrough.ru.md"),
    ("docs/screenshots/README.md", "docs/screenshots/README.ru.md"),
]


def _head(path: Path, n: int = 1500) -> str:
    return path.read_text(encoding="utf-8")[:n]


def check(root: Path = ROOT) -> list[str]:
    """Return a list of problems (empty when all good)."""
    problems: list[str] = []
    for en_rel, ru_rel in DOC_PAIRS:
        en, ru = root / en_rel, root / ru_rel
        en_name, ru_name = Path(en_rel).name, Path(ru_rel).name

        if not en.exists():
            problems.append(f"missing English doc: {en_rel}")
        if not ru.exists():
            problems.append(f"missing Russian doc: {ru_rel}")
        if not en.exists() or not ru.exists():
            continue

        # English doc must link to its Russian sibling.
        if f"[Русский](./{ru_name})" not in _head(en):
            problems.append(f"{en_rel}: missing switch link to ./{ru_name}")
        # Russian doc must link back to its English sibling.
        if f"[🇺🇸English](./{en_name})" not in _head(ru):
            problems.append(f"{ru_rel}: missing switch link to ./{en_name}")
    return problems


def main() -> int:
    problems = check()
    print("Docs link check")
    print("=" * 48)
    if problems:
        for p in problems:
            print("  PROBLEM:", p)
        print("-" * 48)
        print(f"{len(problems)} problem(s) found.")
        return 1
    print(f"  {len(DOC_PAIRS)} doc pairs OK (EN <-> RU + switch links).")
    print("All documentation links are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

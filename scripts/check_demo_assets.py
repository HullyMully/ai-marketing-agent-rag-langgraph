"""Verify that all expected demo visual assets exist and are non-empty.

No external dependencies – safe to run anywhere (including CI):

    python scripts/check_demo_assets.py

Exits with code 0 if every asset is present and looks like valid SVG,
otherwise prints what's missing and exits with code 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ASSETS: list[str] = [
    # diagrams
    "docs/assets/social-preview.svg",
    "docs/assets/architecture-overview.svg",
    "docs/assets/langgraph-flow.svg",
    "docs/assets/rag-pipeline.svg",
    # screenshot mockups
    "docs/screenshots/demo-chat.svg",
    "docs/screenshots/crm-lead-created.svg",
    "docs/screenshots/escalation-ticket.svg",
    "docs/screenshots/demo-metrics.svg",
    "docs/screenshots/api-overview.svg",
]

MIN_BYTES = 500  # a real asset is comfortably larger than this


def check_assets(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return (ok, problems) lists of asset descriptions."""
    ok: list[str] = []
    problems: list[str] = []
    for rel in EXPECTED_ASSETS:
        path = root / rel
        if not path.exists():
            problems.append(f"MISSING  {rel}")
            continue
        data = path.read_text(encoding="utf-8", errors="ignore")
        size = path.stat().st_size
        if size < MIN_BYTES:
            problems.append(f"TOO SMALL {rel} ({size} bytes)")
        elif "<svg" not in data:
            problems.append(f"NOT SVG  {rel}")
        else:
            ok.append(f"OK  {rel} ({size} bytes)")
    return ok, problems


def main() -> int:
    ok, problems = check_assets()
    print("Demo asset check")
    print("=" * 48)
    for line in ok:
        print("  " + line)
    for line in problems:
        print("  " + line)
    print("-" * 48)
    print(f"{len(ok)}/{len(EXPECTED_ASSETS)} assets present and valid.")
    if problems:
        print("FAILED: some assets are missing or invalid.")
        return 1
    print("All demo assets present. ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

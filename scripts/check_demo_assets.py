"""Verify that all expected demo visual assets exist and are non-empty.

No external dependencies – safe to run anywhere (including CI):

    python scripts/check_demo_assets.py

Exits with code 0 if every asset is present and looks like valid SVG,
otherwise prints what's missing and exits with code 1.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ASSETS: list[str] = [
    # diagrams
    "docs/assets/social-preview.svg",
    "docs/assets/architecture-overview.svg",
    "docs/assets/langgraph-flow.svg",
    "docs/assets/rag-pipeline.svg",
    # real product screenshots (PNG) — these are what the README displays
    "docs/screenshots/landing-page.png",
    "docs/screenshots/web-chat-lead-flow.png",
    "docs/screenshots/admin-knowledge-base.png",
    "docs/screenshots/admin-operations.png",
    "docs/screenshots/api-overview.png",
    "docs/screenshots/metrics-dashboard.png",
]

MIN_BYTES = 500  # a real asset is comfortably larger than this
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def check_assets(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Return (ok, problems) lists of asset descriptions.

    SVG diagrams must contain an ``<svg`` tag; PNG screenshots must start with
    the PNG signature. Both must be comfortably non-empty.
    """
    ok: list[str] = []
    problems: list[str] = []
    for rel in EXPECTED_ASSETS:
        path = root / rel
        if not path.exists():
            problems.append(f"MISSING  {rel}")
            continue
        size = path.stat().st_size
        if size < MIN_BYTES:
            problems.append(f"TOO SMALL {rel} ({size} bytes)")
        elif rel.endswith(".png"):
            if path.read_bytes()[:8] != _PNG_MAGIC:
                problems.append(f"NOT PNG  {rel}")
            else:
                ok.append(f"OK  {rel} ({size} bytes)")
        elif "<svg" not in path.read_text(encoding="utf-8", errors="ignore"):
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

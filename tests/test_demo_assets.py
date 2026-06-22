"""Smoke test: all demo visual assets exist and are valid SVG."""
from scripts.check_demo_assets import EXPECTED_ASSETS, check_assets


def test_all_demo_assets_present() -> None:
    ok, problems = check_assets()
    assert not problems, f"Demo asset problems: {problems}"
    assert len(ok) == len(EXPECTED_ASSETS)

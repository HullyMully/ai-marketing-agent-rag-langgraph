"""Test that bilingual documentation is consistent."""
from scripts.check_docs_links import DOC_PAIRS, check


def test_all_doc_pairs_present_and_linked() -> None:
    problems = check()
    assert not problems, "Doc link problems: " + "; ".join(problems)
    assert len(DOC_PAIRS) >= 10

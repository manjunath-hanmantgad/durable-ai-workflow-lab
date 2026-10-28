"""The manifest describes scenarios; this test does not execute them."""

import json
from pathlib import Path


MANIFEST = Path(__file__).resolve().parents[2] / "fixtures" / "cases.json"


def test_twenty_unique_case_definitions():
    assert MANIFEST.is_file(), "Create the versioned synthetic case manifest"
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["version"] == 1
    cases = manifest["cases"]
    assert len(cases) >= 20
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert {f"C{number:02}" for number in range(1, 25)} <= set(ids)
    for case in cases:
        assert case["scenario"].strip()
        assert case["expected_outcome"].strip()
        assert case["owning_task"] in (2, 3, 4, 5)
        assert case["status"] == "planned"

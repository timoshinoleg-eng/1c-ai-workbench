# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Provider-free tests for the Thin Client extensions to the PRISM eval.

The full ``scripts/26_run_prism_eval.py`` run needs the release ``bsl-indexer``
binary and executes in CI (the rust-build job). These tests exercise the pure
retrieval-discipline helpers and the cases definition without the binary, so the
exact-match / absence contract is verified locally as well.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "code-index-045"
CASES = ROOT / "evals" / "prism-1c" / "cases.json"
MODULE_BSL = "CommonModules/ПилотИндекса/Ext/Module.bsl"

sys.path.insert(0, str(SCRIPTS_DIR))
prism = importlib.import_module("26_run_prism_eval")


# ── assert_absence: exact-match discipline ─────────────────────────────────


def test_assert_absence_passes_when_no_exact_match() -> None:
    payload = {"functions": [{"name": "РассчитатьСумму"}]}
    # A similar-but-different name must not count as an exact hit.
    prism.assert_absence(payload, "РассчитатьСумма")


def test_assert_absence_passes_on_empty_index() -> None:
    prism.assert_absence({"functions": []}, "НесуществующийМетод")


def test_assert_absence_fails_when_symbol_exists() -> None:
    payload = {"functions": [{"name": "РассчитатьСумму"}]}
    with pytest.raises(AssertionError, match="similar name must not substitute"):
        prism.assert_absence(payload, "РассчитатьСумму")


def test_assert_absence_ignores_other_functions() -> None:
    payload = {"functions": [{"name": "ВыполнитьПроверку"}, {"name": "РассчитатьСумму"}]}
    with pytest.raises(AssertionError):
        prism.assert_absence(payload, "ВыполнитьПроверку")


# ── assert_citation: evidence must be real ─────────────────────────────────


def test_assert_citation_accepts_supported_evidence() -> None:
    citation = {"path": MODULE_BSL, "line_start": 2, "line_end": 4, "must_contain": "РассчитатьСумму"}
    result = prism.assert_citation(FIXTURE, citation)
    assert result["path"] == MODULE_BSL
    assert result["line_start"] == 2


def test_assert_citation_rejects_wrong_token() -> None:
    citation = {"path": MODULE_BSL, "line_start": 2, "line_end": 4, "must_contain": "НетТакогоТокена"}
    with pytest.raises(AssertionError, match="does not support evidence token"):
        prism.assert_citation(FIXTURE, citation)


def test_assert_citation_rejects_invalid_range() -> None:
    citation = {"path": MODULE_BSL, "line_start": 100, "line_end": 200, "must_contain": "РассчитатьСумму"}
    with pytest.raises(AssertionError, match="Invalid citation range"):
        prism.assert_citation(FIXTURE, citation)


def test_assert_citation_rejects_missing_source() -> None:
    citation = {"path": "CommonModules/Нет/Module.bsl", "line_start": 1, "line_end": 1, "must_contain": "x"}
    with pytest.raises(AssertionError, match="missing"):
        prism.assert_citation(FIXTURE, citation)


# ── render_markdown tolerates absence cases (citation is null) ─────────────


def test_render_markdown_handles_absence_cases() -> None:
    report = {
        "verdict": "PASS",
        "score": 2,
        "max_score": 2,
        "cases": [
            {"id": "exact", "kind": "symbol", "score": 1, "citation": {"path": MODULE_BSL, "line_start": 2, "line_end": 4}},
            {"id": "absent", "kind": "absence", "score": 1, "citation": None, "evidence": "no exact symbol for query 'X'"},
        ],
    }
    rendered = prism.render_markdown(report)
    assert "exact" in rendered
    assert "absent" in rendered
    assert "no exact symbol" in rendered


# ── cases.json contract ────────────────────────────────────────────────────


def _cases() -> dict:
    return json.loads(CASES.read_text(encoding="utf-8"))


def test_suite_is_provider_free() -> None:
    definition = _cases()
    assert definition["network_required"] is False
    assert definition["provider_credentials_required"] is False


def test_thin_client_cases_are_present() -> None:
    ids = {case["id"] for case in _cases()["cases"]}
    assert {"thin-client-exact-retrieval", "thin-client-similar-name-trap", "thin-client-absent-symbol"}.issubset(ids)


def test_absence_cases_carry_a_query() -> None:
    absence = [case for case in _cases()["cases"] if case["kind"] == "absence"]
    assert len(absence) >= 2
    for case in absence:
        assert isinstance(case.get("query"), str) and case["query"]


def test_symbol_cases_carry_citation_and_expected_symbol() -> None:
    symbols = [case for case in _cases()["cases"] if case["kind"] in {"symbol", "body"}]
    assert symbols
    for case in symbols:
        assert case["expected_symbol"]
        assert case["citation"]["path"]
        assert case["citation"]["must_contain"]

# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_gitleaks_scan_is_bounded_to_the_trigger_ref() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    required_context = (
        "GITLEAKS_EVENT_NAME: ${{ github.event_name }}",
        "GITLEAKS_BASE_SHA: ${{ github.event.pull_request.base.sha }}",
        "GITLEAKS_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}",
        "GITLEAKS_BEFORE_SHA: ${{ github.event.before }}",
    )
    for context in required_context:
        assert context in workflow

    required_ranges = (
        'log_opts="$GITLEAKS_BASE_SHA..$GITLEAKS_HEAD_SHA"',
        'log_opts="$GITLEAKS_BEFORE_SHA..$GITLEAKS_HEAD_SHA"',
        'log_opts="$GITLEAKS_HEAD_SHA"',
    )
    for commit_range in required_ranges:
        assert commit_range in workflow

    assert '[[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]' in workflow
    assert '*)\n              echo "::error::Unsupported event for gitleaks:' in workflow
    assert '--log-opts="$log_opts"' in workflow
    assert "./gitleaks git --redact --verbose ." not in workflow


def test_gitleaks_keeps_full_history_available_for_bounded_ranges() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow

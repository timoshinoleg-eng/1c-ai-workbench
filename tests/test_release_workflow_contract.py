# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CANDIDATE = WORKFLOWS / "build-candidate.yml"
PUBLISH = WORKFLOWS / "publish-verified.yml"


def workflow_text(path: Path) -> str:
    assert path.is_file(), f"Required release workflow is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def test_monolithic_release_workflow_is_retired() -> None:
    assert not (WORKFLOWS / "release.yml").exists()


def test_candidate_build_does_not_publish_or_create_tags() -> None:
    candidate = workflow_text(CANDIDATE)

    assert "workflow_dispatch:" in candidate
    assert "environment: release-candidate" in candidate
    assert "actions/upload-artifact" in candidate
    assert "candidate-manifest.json" in candidate
    assert "checksums.txt" in candidate
    assert "gh release create" not in candidate
    assert "git tag " not in candidate
    assert "refs/tags/" not in candidate


def test_publisher_uses_verified_artifact_without_rebuilding() -> None:
    publish = workflow_text(PUBLISH)

    assert "environment: production-release" in publish
    assert "candidate_run_id:" in publish
    assert "verification_record:" in publish
    assert "gh run download" in publish
    assert "candidate-manifest.json" in publish
    assert "Get-AuthenticodeSignature" in publish
    assert "git merge-base --is-ancestor" in publish
    assert "gh release create" in publish

    forbidden_rebuild_commands = (
        "cargo build",
        "19_build_windows_installer.ps1",
        "Import-PfxCertificate",
        "signtool sign",
    )
    for command in forbidden_rebuild_commands:
        assert command not in publish


def test_release_actions_are_pinned_to_full_commits() -> None:
    action_reference = re.compile(r"^\s*-\s+uses:\s+(\S+)", re.MULTILINE)

    for workflow in (CANDIDATE, PUBLISH):
        for reference in action_reference.findall(workflow_text(workflow)):
            assert re.search(r"@[0-9a-f]{40}$", reference), (
                f"{workflow.name} contains an unpinned action: {reference}"
            )

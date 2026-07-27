# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT

"""Regression contract for the separate unsigned beta release contour.

These tests pin the safety properties of ``build-beta-candidate.yml`` and
``publish-beta-verified.yml`` without touching the signed production contour
(``build-candidate.yml`` / ``publish-verified.yml``), which is covered by
``test_release_workflow_contract.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BETA_CANDIDATE = WORKFLOWS / "build-beta-candidate.yml"
BETA_PUBLISH = WORKFLOWS / "publish-beta-verified.yml"
PROD_CANDIDATE = WORKFLOWS / "build-candidate.yml"
PROD_PUBLISH = WORKFLOWS / "publish-verified.yml"

PRODUCTION_APP_ID = "8F3E09B8-5D2F-4B98-8EA4-1C0A1F0B1C01"

SIGNING_OPERATIONS = (
    "Import-PfxCertificate",
    "signtool sign",
    "SignCertificateThumbprint",
    "New-SelfSignedCertificate",
    "SIGNING_PFX",
    "SIGNING_THUMBPRINT",
    "WINDOWS_SIGNING_CERT",
)

REBUILD_OPERATIONS = (
    "cargo build",
    "19_build_windows_installer.ps1",
    "23_prepare_offline_wheelhouse.ps1",
    "Import-PfxCertificate",
    "signtool sign",
)


def workflow_text(path: Path) -> str:
    assert path.is_file(), f"Required beta workflow is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def test_beta_workflows_exist_and_production_contour_intact() -> None:
    assert BETA_CANDIDATE.is_file()
    assert BETA_PUBLISH.is_file()
    # The signed production contour must remain present and separate.
    assert PROD_CANDIDATE.is_file()
    assert PROD_PUBLISH.is_file()


def test_beta_build_does_not_publish_or_create_tags() -> None:
    beta = workflow_text(BETA_CANDIDATE)

    assert "workflow_dispatch:" in beta
    assert "actions/upload-artifact" in beta
    assert "beta-manifest.json" in beta
    assert "checksums.txt" in beta
    assert "gh release create" not in beta
    assert "git tag " not in beta
    assert "refs/tags/" not in beta
    assert "--prerelease" not in beta


def test_beta_build_is_unsigned_and_has_no_signing_material() -> None:
    beta = workflow_text(BETA_CANDIDATE)

    for operation in SIGNING_OPERATIONS:
        assert operation not in beta, f"beta build must not reference {operation}"
    # A signing-protected environment must not gate the unsigned beta build.
    assert "environment:" not in beta

    # Positive honesty markers: the manifest must declare the artifact unsigned.
    assert "release_channel = 'beta'" in beta
    assert "signed = $false" in beta
    assert "authenticode_present = $false" in beta
    assert "Assert beta installer is unsigned" in beta


def test_beta_build_requires_frozen_main_and_prerelease_version() -> None:
    beta = workflow_text(BETA_CANDIDATE)

    assert "refs/heads/main" in beta
    assert "frozen origin/main" in beta
    # The version gate must require a SemVer prerelease suffix so this workflow
    # can never produce a stable release.
    assert r"-(0|[1-9A-Za-z-][0-9A-Za-z-.]*)$" in beta


def test_beta_build_uses_isolated_app_id() -> None:
    beta = workflow_text(BETA_CANDIDATE)

    assert "BETA_APP_ID" in beta
    # The beta installer must not reuse the production application id, so a beta
    # install can never upgrade or overwrite a production installation.
    assert PRODUCTION_APP_ID not in beta


def test_beta_build_runs_mandatory_tests_and_contracts() -> None:
    beta = workflow_text(BETA_CANDIDATE)

    assert "python -m pytest -q" in beta
    assert "cargo test --all --no-fail-fast" in beta
    assert "25_validate_code_index_045.py" in beta
    assert "26_run_prism_eval.py" in beta
    assert "24_test_windows_installer.ps1" in beta


def test_beta_publish_uses_verified_artifact_without_rebuilding() -> None:
    publish = workflow_text(BETA_PUBLISH)

    assert "candidate_run_id:" in publish
    assert "verification_record:" in publish
    assert "gh run download" in publish
    assert "beta-manifest.json" in publish
    assert "gh release create" in publish

    for command in REBUILD_OPERATIONS:
        assert command not in publish, f"beta publish must not rebuild: {command}"


def test_beta_publish_is_unsigned_contour() -> None:
    publish = workflow_text(BETA_PUBLISH)

    for operation in SIGNING_OPERATIONS:
        assert operation not in publish, f"beta publish must not reference {operation}"
    # The publisher re-asserts the artifact is unsigned before publishing.
    assert "must be unsigned" in publish
    assert "Get-AuthenticodeSignature" in publish
    assert "signed -ne $false" in publish or "manifest.signed -ne $false" in publish


def test_beta_publish_requires_prerelease_tag_and_flag() -> None:
    publish = workflow_text(BETA_PUBLISH)

    # Tag gate must require a SemVer prerelease suffix.
    assert r"(0|[1-9A-Za-z-][0-9A-Za-z-.]*)" in publish
    # The GitHub Release must be created with the prerelease flag.
    assert "--prerelease" in publish


def test_beta_publish_rejects_existing_release_and_tag_conflicts() -> None:
    publish = workflow_text(BETA_PUBLISH)

    assert "gh release view" in publish
    assert "will not be overwritten" in publish
    # Existing tags are validated, never force-moved.
    assert "git tag --list" in publish
    assert "not $env:RELEASE_COMMIT" in publish


def test_beta_publish_verifies_provenance_manifest_and_hashes() -> None:
    publish = workflow_text(BETA_PUBLISH)

    assert "build-beta-candidate.yml" in publish
    assert "workflow_id" in publish
    assert "head_branch" in publish
    assert "head_sha" in publish
    assert "merge-base --is-ancestor" in publish
    assert "SHA-256 mismatch" in publish
    assert "release_channel -ne 'beta'" in publish


def test_beta_actions_are_pinned_to_full_commits() -> None:
    action_reference = re.compile(r"^\s*-\s+uses:\s+(\S+)", re.MULTILINE)

    for workflow in (BETA_CANDIDATE, BETA_PUBLISH):
        references = action_reference.findall(workflow_text(workflow))
        assert references, f"{workflow.name} declares no actions"
        for reference in references:
            assert re.search(r"@[0-9a-f]{40}$", reference), (
                f"{workflow.name} contains an unpinned action: {reference}"
            )


def test_beta_workflows_parse_as_yaml() -> None:
    yaml = pytest.importorskip("yaml")
    for workflow in (BETA_CANDIDATE, BETA_PUBLISH):
        parsed = yaml.safe_load(workflow_text(workflow))
        assert isinstance(parsed, dict)
        assert "jobs" in parsed

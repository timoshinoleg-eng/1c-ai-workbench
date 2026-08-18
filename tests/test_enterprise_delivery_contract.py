from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_first_run_document_exists_and_avoids_global_bypass():
    content = (ROOT / "docs" / "ENTERPRISE_FIRST_RUN.md").read_text(encoding="utf-8")
    assert "Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned" in content
    assert "MachinePolicy" in content
    assert "offline-wheelhouse" in content
    assert "Get-AuthenticodeSignature" in content


def test_start_here_validates_local_dump_path_before_creation():
    content = (ROOT / "START_HERE.ps1").read_text(encoding="utf-8")
    assert "function Resolve-LocalDumpPath" in content
    assert "$DumpPath = Resolve-LocalDumpPath $DumpPath" in content
    assert "UNC and device paths are not allowed" in content
    assert content.index("$DumpPath = Resolve-LocalDumpPath $DumpPath") < content.index("function Show-DumpFolder")


def test_release_evidence_script_is_read_only():
    content = (ROOT / "scripts" / "28_collect_release_evidence.ps1").read_text(encoding="utf-8")
    assert "Get-FileHash" in content
    assert "Get-AuthenticodeSignature" in content
    assert "--version" in content
    assert "Set-AuthenticodeSignature" not in content
    assert "Publish-" not in content


def test_pilot_package_documents_are_present():
    for relative in [
        "docs/PILOT_RUNBOOK.md",
        "docs/PILOT_ACCEPTANCE_CHECKLIST.md",
        "docs/RELEASE_EVIDENCE.md",
        "docs/COMMERCIAL.md",
        "docs/FEATURE_GAP_MAP.md",
        "docs/SCRIPT_CATALOG.md",
    ]:
        assert (ROOT / relative).is_file(), relative

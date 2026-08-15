# SPDX-FileCopyrightText: 2026 1C AI Workbench contributors
#
# SPDX-License-Identifier: MIT
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer" / "1c-ai-workbench.iss"
BUILD_SCRIPT = ROOT / "scripts" / "19_build_windows_installer.ps1"
SETUP_SCRIPT = ROOT / "scripts" / "setup.ps1"


def text(path: Path) -> str:
    assert path.is_file(), f"Required source file is missing: {path}"
    return path.read_text(encoding="utf-8")


def test_installer_stages_verified_vcruntime140_app_local() -> None:
    build = text(BUILD_SCRIPT)
    installer = text(INSTALLER)
    assert "function Stage-VcRuntime140" in build
    assert '"System32\\VCRUNTIME140.dll"' in build
    assert "Get-AuthenticodeSignature" in build
    assert 'SignerCertificate.Subject -notmatch "Microsoft"' in build
    assert "$env:VCRUNTIME140_DLL = Stage-VcRuntime140" in build
    assert 'VCRUNTIME140_DLL' in installer
    assert 'DestDir: "{app}\\tools\\code-index-mcp\\target\\release"' in installer
    assert 'DestName: "VCRUNTIME140.dll"' in installer


def test_setup_contract_requires_full_cpython_311_x64() -> None:
    setup = text(SETUP_SCRIPT)
    assert "64-bit CPython 3.11 not found" in setup
    assert "Offline setup requires 64-bit CPython 3.11" in setup
    assert "venv" in setup
    assert "Python 3.10+ not found" not in setup

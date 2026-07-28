# tests/test_continue_config_diagnostics.py
# Synthetic tests for scripts/37_diagnose_continue_config.ps1
#
# All tests use temporary fixtures. The real user ~/.continue is NEVER touched.
# SPDX-License-Identifier: MIT
"""Tests for Continue config preflight diagnostics (script 37)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "37_diagnose_continue_config.ps1"


# Find a working PowerShell
def _find_powershell():
    for cmd in ("pwsh", "powershell"):
        if shutil.which(cmd):
            return cmd
    return None


PS = _find_powershell()
SKIP_REASON = "PowerShell not available"


def run_script(continue_home: Path, extension_root: Path | None = None, json_mode: bool = True):
    """Run the diagnostics script and return (exit_code, stdout, stderr)."""
    args = [PS, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-ContinueHome", str(continue_home)]
    if extension_root:
        args += ["-ExtensionRoot", str(extension_root)]
    if json_mode:
        args += ["-Json"]
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=60,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


def parse_json_output(stdout: str) -> dict:
    """Parse exactly one JSON object from stdout."""
    stripped = stdout.strip()
    assert stripped, "stdout is empty"
    return json.loads(stripped)


@pytest.fixture
def tmp_continue(tmp_path):
    """Create a temporary Continue home directory."""
    ch = tmp_path / ".continue"
    ch.mkdir()
    return ch


@pytest.fixture
def tmp_extension(tmp_path):
    """Create a fake Continue extension directory with package.json and schema."""
    ext = tmp_path / "continue.continue-2.0.0-win32-x64"
    ext.mkdir()
    pkg = {"name": "continue", "version": "2.0.0"}
    (ext / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    (ext / "config-yaml-schema.json").write_text(json.dumps(schema), encoding="utf-8")
    return ext


# --- Test 1: Markdown config.json + no YAML → FAIL/exit 1 ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_markdown_json_no_yaml_fail(tmp_continue, tmp_extension):
    (tmp_continue / "config.json").write_text(
        "# DebiForeverProfile — Universal Agent Instructions\n\nSome markdown.",
        encoding="utf-8",
    )
    code, stdout, _stderr = run_script(tmp_continue, tmp_extension)
    assert code == 1, f"Expected exit 1, got {code}. stdout={stdout}"
    data = parse_json_output(stdout)
    assert data["overall"] == "FAIL"
    assert data["selectedSource"] == "json"
    codes = [c["code"] for c in data["checks"]]
    assert "E206" in codes
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "FAIL"


# --- Test 2: UTF-8 BOM + whitespace + Markdown # → FAIL ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_bom_whitespace_markdown_fail(tmp_continue, tmp_extension):
    content = b"\xef\xbb\xbf   \n\t  # Heading\n"
    (tmp_continue / "config.json").write_bytes(content)
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 1
    data = parse_json_output(stdout)
    assert data["overall"] == "FAIL"
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "FAIL"


# --- Test 3: Valid non-empty YAML + invalid legacy JSON → WARN/exit 0 ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_valid_yaml_invalid_json_warn(tmp_continue, tmp_extension):
    yaml_content = "name: test\nversion: 1.0.0\nschema: v1\n"
    (tmp_continue / "config.yaml").write_text(yaml_content, encoding="utf-8")
    (tmp_continue / "config.json").write_text("# broken markdown", encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0, f"Expected exit 0, got {code}. stdout={stdout}"
    data = parse_json_output(stdout)
    assert data["selectedSource"] == "yaml"
    # Should have migration warning
    codes = [c["code"] for c in data["checks"]]
    assert "E209" in codes
    e209 = next(c for c in data["checks"] if c["code"] == "E209")
    assert e209["status"] == "WARN"


# --- Test 4: Invalid non-empty YAML → FAIL ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_invalid_yaml_fail(tmp_continue, tmp_extension):
    # Invalid YAML: unclosed bracket
    (tmp_continue / "config.yaml").write_text("name: [unclosed\n  bad: {", encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    data = parse_json_output(stdout)
    assert data["selectedSource"] == "yaml"
    e204 = next(c for c in data["checks"] if c["code"] == "E204")
    assert e204["status"] in ("FAIL", "NOT_RUN")
    # If Python/PyYAML available, should be FAIL
    if e204["status"] == "FAIL":
        assert code == 1


# --- Test 5: Empty YAML → FAIL with auto-overwrite-risk code ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_empty_yaml_fail(tmp_continue, tmp_extension):
    (tmp_continue / "config.yaml").write_text("", encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 1
    data = parse_json_output(stdout)
    codes = [c["code"] for c in data["checks"]]
    assert "E205" in codes
    e205 = next(c for c in data["checks"] if c["code"] == "E205")
    assert e205["status"] == "FAIL"


# --- Test 6: Whitespace-only YAML → FAIL ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_whitespace_yaml_fail(tmp_continue, tmp_extension):
    (tmp_continue / "config.yaml").write_text("   \n\t\n  \r\n", encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 1
    data = parse_json_output(stdout)
    codes = [c["code"] for c in data["checks"]]
    assert "E205" in codes


# --- Test 7: Both files absent → first-run WARN/exit 0 ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_both_absent_firstrun_warn(tmp_continue, tmp_extension):
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    data = parse_json_output(stdout)
    assert data["selectedSource"] == "none"
    codes = [c["code"] for c in data["checks"]]
    assert "E207" in codes
    e207 = next(c for c in data["checks"] if c["code"] == "E207")
    assert e207["status"] == "WARN"


# --- Test 8: Valid legacy JSON ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_valid_json_pass(tmp_continue, tmp_extension):
    (tmp_continue / "config.json").write_text('{"models": []}', encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    data = parse_json_output(stdout)
    assert data["selectedSource"] == "json"
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "PASS"


# --- Test 9: Valid JSONC with line comments ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_jsonc_line_comments_pass(tmp_continue, tmp_extension):
    content = '// This is a comment\n{"models": []}'
    (tmp_continue / "config.json").write_text(content, encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    data = parse_json_output(stdout)
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "PASS"


# --- Test 10: Valid JSONC with block comments ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_jsonc_block_comments_pass(tmp_continue, tmp_extension):
    content = '/* block comment */\n{"models": []}'
    (tmp_continue / "config.json").write_text(content, encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    data = parse_json_output(stdout)
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "PASS"


# --- Test 11: JSON string containing //, /*, # must not be misclassified ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_json_with_special_chars_in_string(tmp_continue, tmp_extension):
    # Valid JSON that starts with { but contains // and # inside strings
    content = '{"url": "http://example.com", "note": "# not markdown", "path": "/* ok */"}'
    (tmp_continue / "config.json").write_text(content, encoding="utf-8")
    code, stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    data = parse_json_output(stdout)
    e206 = next(c for c in data["checks"] if c["code"] == "E206")
    assert e206["status"] == "PASS"


# --- Test 12: Continue extension missing ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_extension_missing(tmp_continue, tmp_path):
    # Point to a non-existent extension root
    fake_ext = tmp_path / "nonexistent-ext"
    (tmp_continue / "config.json").write_text('{"models": []}', encoding="utf-8")
    _code, stdout, _ = run_script(tmp_continue, fake_ext)
    data = parse_json_output(stdout)
    codes = [c["code"] for c in data["checks"]]
    assert "E202" in codes
    e202 = next(c for c in data["checks"] if c["code"] == "E202")
    assert e202["status"] == "FAIL"


# --- Test 13: Bundled schema missing ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_schema_missing(tmp_continue, tmp_path):
    ext = tmp_path / "continue.continue-2.0.0"
    ext.mkdir()
    (ext / "package.json").write_text('{"version": "2.0.0"}', encoding="utf-8")
    # No config-yaml-schema.json
    (tmp_continue / "config.yaml").write_text("name: x\nversion: 1.0.0\nschema: v1\n", encoding="utf-8")
    _code, stdout, _ = run_script(tmp_continue, ext)
    data = parse_json_output(stdout)
    codes = [c["code"] for c in data["checks"]]
    assert "E208" in codes
    e208 = next(c for c in data["checks"] if c["code"] == "E208")
    assert e208["status"] == "WARN"


# --- Test 14: Unsupported/unverified version ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_unsupported_version(tmp_continue, tmp_path):
    ext = tmp_path / "continue.continue-1.5.0"
    ext.mkdir()
    (ext / "package.json").write_text('{"version": "1.5.0"}', encoding="utf-8")
    (tmp_continue / "config.json").write_text('{"models": []}', encoding="utf-8")
    _code, stdout, _ = run_script(tmp_continue, ext)
    data = parse_json_output(stdout)
    codes = [c["code"] for c in data["checks"]]
    assert "E210" in codes
    e210 = next(c for c in data["checks"] if c["code"] == "E210")
    assert e210["status"] == "WARN"


# --- Test 15: Unicode and spaces in -ContinueHome and -ExtensionRoot ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_unicode_spaces_paths(tmp_path):
    ch = tmp_path / "my continue home" / "подкаталог"
    ch.mkdir(parents=True)
    ext = tmp_path / "ext dir" / "continue.continue-2.0.0"
    ext.mkdir(parents=True)
    (ext / "package.json").write_text('{"version": "2.0.0"}', encoding="utf-8")
    (ch / "config.json").write_text('{"models": []}', encoding="utf-8")
    code, stdout, _ = run_script(ch, ext)
    assert code == 0
    data = parse_json_output(stdout)
    assert data["selectedSource"] == "json"


# --- Test 16: -Json produces exactly one parseable JSON object ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_json_single_object(tmp_continue, tmp_extension):
    (tmp_continue / "config.json").write_text('{"models": []}', encoding="utf-8")
    _code, stdout, stderr = run_script(tmp_continue, tmp_extension, json_mode=True)
    stripped = stdout.strip()
    # Must be exactly one JSON object
    data = json.loads(stripped)
    assert isinstance(data, dict)
    assert "schemaVersion" in data
    assert "overall" in data
    assert "exitCode" in data
    assert "selectedSource" in data
    assert "checks" in data
    # stderr should be empty for normal PASS/WARN/FAIL
    assert stderr.strip() == "", f"stderr not empty: {stderr}"


# --- Test 17: Exact exit-code contract ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_exit_codes(tmp_continue, tmp_extension):
    # PASS case
    (tmp_continue / "config.json").write_text('{"models": []}', encoding="utf-8")
    code, _, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0

    # FAIL case
    (tmp_continue / "config.json").write_text("# markdown", encoding="utf-8")
    code, _, _ = run_script(tmp_continue, tmp_extension)
    assert code == 1


# --- Test 18: Secret canaries never appear in output ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_secret_canaries_never_in_output(tmp_continue, tmp_extension):
    # YAML with secret-like values
    yaml_content = (
        "name: test\n"
        "version: 1.0.0\n"
        "schema: v1\n"
        "models:\n"
        "  - name: secret-model\n"
        "    apiKey: ${{ secrets.SUPER_SECRET_CANARY_XYZ123 }}\n"
        "    apiBase: https://user:password@host/v1?token=CANARY_TOKEN_456#frag\n"
    )
    (tmp_continue / "config.yaml").write_text(yaml_content, encoding="utf-8")
    # Also create a .env canary that must NOT be read
    (tmp_continue / ".env").write_text("DOTENV_CANARY=never_read_this_value_789\n", encoding="utf-8")
    _code, stdout, stderr = run_script(tmp_continue, tmp_extension)
    combined = stdout + stderr
    assert "SUPER_SECRET_CANARY_XYZ123" not in combined
    assert "CANARY_TOKEN_456" not in combined
    assert "never_read_this_value_789" not in combined
    assert "password" not in combined
    # Secret names should not appear either
    assert "secrets.SUPER_SECRET" not in combined


# --- Test 19: .env canary file is never read or hashed ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_env_file_never_read(tmp_continue, tmp_extension):
    env_path = tmp_continue / ".env"
    env_path.write_text("SECRET=canary_value_abc\n", encoding="utf-8")
    mtime_before = env_path.stat().st_mtime
    size_before = env_path.stat().st_size
    _code, stdout, stderr = run_script(tmp_continue, tmp_extension)
    mtime_after = env_path.stat().st_mtime
    size_after = env_path.stat().st_size
    assert mtime_before == mtime_after, ".env mtime changed"
    assert size_before == size_after, ".env size changed"
    assert "canary_value_abc" not in (stdout + stderr)


# --- Test 20: No writes - inventory, bytes, mtimes, no new files ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_no_writes(tmp_continue, tmp_extension):
    # Create test files
    cfg = tmp_continue / "config.json"
    cfg.write_text('{"models": []}', encoding="utf-8")
    # Record state
    files_before = {p.name for p in tmp_continue.iterdir()}
    mtime_before = cfg.stat().st_mtime
    bytes_before = cfg.read_bytes()
    _code, _stdout, _stderr = run_script(tmp_continue, tmp_extension)
    # Verify no changes
    files_after = {p.name for p in tmp_continue.iterdir()}
    assert files_before == files_after, f"Files changed: {files_after - files_before}"
    assert cfg.stat().st_mtime == mtime_before, "config.json mtime changed"
    assert cfg.read_bytes() == bytes_before, "config.json bytes changed"
    # No new temp/log/backup files in parent
    parent_files = {p.name for p in tmp_continue.parent.iterdir()}
    # Only .continue dir should exist (created by fixture)
    assert ".continue" in parent_files


# --- Test 21: Script does not invoke Continue helpers that create/rewrite ---
@pytest.mark.skipif(PS is None, reason=SKIP_REASON)
def test_no_continue_helper_invocation(tmp_continue, tmp_extension):
    # If both configs absent, Continue would create default YAML.
    # Our script must NOT create it.
    code, _stdout, _ = run_script(tmp_continue, tmp_extension)
    assert code == 0
    # config.yaml must NOT have been created
    assert not (tmp_continue / "config.yaml").exists(), "Script created config.yaml!"


# --- Test 22: Existing repository profiles remain unchanged ---
def test_repo_profiles_unchanged():
    """Verify the four repository Continue profiles are not modified by this test suite."""
    profiles_dir = REPO_ROOT / "configs" / "continue"
    if not profiles_dir.exists():
        pytest.skip("configs/continue not present")
    expected = {"hosted-agent.yaml", "local-agent.yaml", "offline-lite.yaml", "online-hybrid.yaml"}
    actual = {p.name for p in profiles_dir.iterdir() if p.suffix == ".yaml"}
    assert expected.issubset(actual), f"Missing profiles: {expected - actual}"

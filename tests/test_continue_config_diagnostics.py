# tests/test_continue_config_diagnostics.py
# Synthetic tests for scripts/37_diagnose_continue_config.ps1.
# The real user Continue directory is never touched.
# SPDX-License-Identifier: MIT
"""Tests for the fail-closed Continue config preflight."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "37_diagnose_continue_config.ps1"
DOCS = (
    REPO_ROOT / "docs" / "PRODUCTION_ONBOARDING_SPEC.md",
    REPO_ROOT / "docs" / "PRODUCTION_ACCEPTANCE_MATRIX.md",
)
RUNTIME_NAMES = ("powershell.exe", "pwsh.exe")
AVAILABLE_RUNTIMES = tuple(path for name in RUNTIME_NAMES if (path := shutil.which(name)))
RUNTIME_PARAMS = AVAILABLE_RUNTIMES or (pytest.param(None, marks=pytest.mark.skip(reason="PowerShell is unavailable")),)
FIXED_INTERNAL_RU = "Внутренняя ошибка диагностики. Детали скрыты."
FIXED_INTERNAL_EN = "Internal diagnostics error. Details are redacted."


@pytest.fixture(params=RUNTIME_PARAMS, ids=lambda value: Path(value).name if value else "missing")
def ps_runtime(request) -> str:
    """Return each installed PowerShell runtime independently."""
    return request.param


@pytest.fixture
def continue_home(tmp_path: Path) -> Path:
    """Create an isolated synthetic Continue home."""
    path = tmp_path / "continue parent" / ".continue"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def extension_factory(tmp_path: Path):
    """Create synthetic Continue extensions with a small deterministic schema."""

    def create(version: str = "2.0.0", *, schema: bool = True, root: Path | None = None) -> Path:
        extension = root or (tmp_path / "extensions" / f"continue.continue-{version}-win32-x64")
        extension.mkdir(parents=True)
        package = {"name": "continue", "version": version}
        (extension / "package.json").write_text(json.dumps(package), encoding="utf-8")
        if schema:
            schema_document = {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
            (extension / "config-yaml-schema.json").write_text(
                json.dumps(schema_document),
                encoding="utf-8",
            )
        return extension

    return create


def run_script(
    runtime: str,
    home: Path,
    extension: Path | None,
    *,
    python_executable: Path | str | None = Path(sys.executable),
    json_mode: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run script 37 with explicit local fixtures."""
    args = [
        runtime,
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT),
        "-ContinueHome",
        str(home),
    ]
    if extension is not None:
        args.extend(("-ExtensionRoot", str(extension)))
    if python_executable is not None:
        args.extend(("-PythonExecutable", str(python_executable)))
    if json_mode:
        args.append("-Json")
    process_environment = os.environ.copy()
    process_environment["PYTHONUTF8"] = "1"
    if environment:
        process_environment.update(environment)
    return subprocess.run(
        args,
        capture_output=True,
        timeout=60,
        encoding="utf-8-sig",
        errors="strict",
        env=process_environment,
    )


def parse_output(result: subprocess.CompletedProcess[str]) -> dict:
    """Parse the single JSON object emitted by script 37."""
    assert result.stdout.strip(), f"stdout is empty; stderr={result.stderr!r}"
    return json.loads(result.stdout.strip())


def check(data: dict, code: str) -> dict:
    """Return one result by error code."""
    return next(item for item in data["checks"] if item["code"] == code)


def write_valid_yaml(home: Path) -> None:
    """Write a schema-valid synthetic config."""
    (home / "config.yaml").write_text("name: test\n", encoding="utf-8")


def snapshot_tree(root: Path) -> dict[str, tuple]:
    """Capture names, bytes, mtimes, modes, and sizes below a fixture root."""
    snapshot: dict[str, tuple] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        if path.is_file():
            snapshot[relative] = ("file", stat.st_mode, stat.st_mtime_ns, stat.st_size, path.read_bytes())
        else:
            snapshot[relative] = ("dir", stat.st_mode, stat.st_mtime_ns)
    return snapshot


def test_required_windows_powershell_runtimes_are_installed() -> None:
    """Do not claim PS 5.1/7 coverage without both actual Windows runtimes."""
    if os.name != "nt":
        pytest.skip("Windows-only runtime availability contract")
    missing = [name for name in RUNTIME_NAMES if shutil.which(name) is None]
    assert not missing, f"Missing required PowerShell runtimes: {missing}"


def test_script_parses_in_each_runtime(ps_runtime: str) -> None:
    """Parse the file with the parser from each runtime."""
    command = (
        "$tokens=$null; $errors=$null; "
        f"$null=[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}',[ref]$tokens,[ref]$errors); "
        "if($errors){$errors | ForEach-Object {$_.Message}; exit 1}; exit 0"
    )
    result = subprocess.run(
        [ps_runtime, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        timeout=30,
        encoding="utf-8-sig",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_markdown_json_without_yaml_fails(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    (continue_home / "config.json").write_text("# Markdown profile\nsecret-canary", encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert data["overall"] == "FAIL"
    assert data["selectedSource"] == "json"
    assert check(data, "E206")["status"] == "FAIL"
    assert "secret-canary" not in result.stdout + result.stderr


def test_bom_whitespace_markdown_fails(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    (continue_home / "config.json").write_bytes(b"\xef\xbb\xbf  \r\n\t# Markdown\n")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E206")["status"] == "FAIL"


def test_exact_200_valid_yaml_can_pass(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory("2.0.0"))
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "PASS"
    assert check(data, "E210")["status"] == "PASS"
    assert check(data, "E204")["status"] == "PASS"
    assert check(data, "E212")["status"] == "PASS"
    assert check(data, "E211")["status"] == "NOT_RUN"


def test_valid_yaml_with_invalid_legacy_json_is_migration_warn(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    (continue_home / "config.json").write_text("# legacy", encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    migration = check(data, "E209")
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert migration["status"] == "WARN"
    assert "fallback" not in migration["messageEn"].lower()


def test_malformed_yaml_fails_with_available_parser(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    (continue_home / "config.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert data["overall"] == "FAIL"
    assert check(data, "E204")["status"] == "FAIL"


def test_schema_invalid_yaml_fails(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    (continue_home / "config.yaml").write_text("name: 42\n", encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E204")["status"] == "PASS"
    assert check(data, "E212")["status"] == "FAIL"


@pytest.mark.parametrize("content", ("", " \r\n\t\n "))
def test_empty_yaml_fails(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    content: str,
) -> None:
    (continue_home / "config.yaml").write_text(content, encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E205")["status"] == "FAIL"


def test_both_configs_absent_is_first_run_warn(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert data["selectedSource"] == "none"
    assert check(data, "E207")["status"] == "WARN"


@pytest.mark.parametrize(
    "content",
    (
        '{"models": []}',
        '// comment\n{"models": []}',
        '/* comment */\n{"models": []}',
        '{"url": "http://example.invalid", "note": "# text"}',
    ),
)
def test_json_jsonc_is_never_claimed_fully_valid(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    content: str,
) -> None:
    (continue_home / "config.json").write_text(content, encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert check(data, "E206")["status"] == "WARN"
    assert check(data, "E213")["status"] == "NOT_RUN"


@pytest.mark.parametrize("content", ("", "  \n", "# markdown", "x-not-json"))
def test_clearly_invalid_json_fails(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    content: str,
) -> None:
    (continue_home / "config.json").write_text(content, encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E206")["status"] == "FAIL"


def test_extension_missing_fails(ps_runtime: str, continue_home: Path, tmp_path: Path) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, tmp_path / "missing")
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E202")["status"] == "FAIL"


def test_schema_missing_is_not_run_and_never_pass(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory(schema=False))
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert check(data, "E208")["status"] == "WARN"
    assert check(data, "E212")["status"] == "NOT_RUN"


def test_missing_yaml_parser_is_not_run_and_never_pass(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows command shim")
    write_valid_yaml(continue_home)
    shim = tmp_path / "missing-python.cmd"
    shim.write_text("@exit /b 20\r\n", encoding="ascii")
    result = run_script(ps_runtime, continue_home, extension_factory(), python_executable=shim)
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert check(data, "E204")["status"] == "NOT_RUN"
    assert check(data, "E212")["status"] == "NOT_RUN"


def test_missing_jsonschema_is_not_run_and_never_pass(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows command shim")
    write_valid_yaml(continue_home)
    counter = tmp_path / "schema-counter.txt"
    shim = tmp_path / "schema-missing.cmd"
    shim.write_text(
        "@echo off\r\n" f'if exist "{counter}" (exit /b 22)\r\n' f'> "{counter}" echo parse-complete\r\n' "exit /b 0\r\n",
        encoding="utf-8",
    )
    result = run_script(ps_runtime, continue_home, extension_factory(), python_executable=shim)
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    assert check(data, "E204")["status"] == "PASS"
    assert check(data, "E212")["status"] == "NOT_RUN"


@pytest.mark.parametrize("version", ("1.9.0", "2.1.0", "2.10.0"))
def test_only_exact_200_is_version_pass(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    version: str,
) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory(version))
    data = parse_output(result)
    assert result.returncode == 0
    assert data["overall"] == "WARN"
    version_check = check(data, "E210")
    assert version_check["status"] == "WARN"
    assert version in version_check["messageEn"]


def test_multiple_versions_use_semantic_not_lexical_order(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    tmp_path: Path,
) -> None:
    write_valid_yaml(continue_home)
    user_profile = tmp_path / "profile"
    extension_base = user_profile / ".vscode" / "extensions"
    for version in ("1.9.0", "2.1.0", "2.10.0"):
        extension_factory(version, root=extension_base / f"continue.continue-{version}")
    result = run_script(
        ps_runtime,
        continue_home,
        None,
        environment={"USERPROFILE": str(user_profile)},
    )
    data = parse_output(result)
    version_check = check(data, "E210")
    assert version_check["status"] == "WARN"
    assert "2.10.0" in version_check["messageEn"]


def test_unicode_and_spaces_in_paths(
    ps_runtime: str,
    tmp_path: Path,
    extension_factory,
) -> None:
    home = tmp_path / "Имя с пробелом" / ".continue"
    home.mkdir(parents=True)
    write_valid_yaml(home)
    extension = extension_factory(root=tmp_path / "Каталог расширения" / "continue.continue-2.0.0")
    result = run_script(ps_runtime, home, extension)
    assert result.returncode == 0
    assert parse_output(result)["overall"] == "PASS"


def test_json_mode_emits_exactly_one_object(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert isinstance(data, dict)
    assert result.stderr == ""
    assert {"schemaVersion", "overall", "exitCode", "selectedSource", "checks"} <= data.keys()


def test_internal_error_is_fixed_redacted_and_exit_2(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    tmp_path: Path,
) -> None:
    extension = extension_factory()
    write_valid_yaml(continue_home)
    shim = tmp_path / "internal-failure.cmd"
    shim.write_text("@exit /b 24\r\n", encoding="ascii")
    result = run_script(
        ps_runtime,
        continue_home,
        extension,
        python_executable=shim,
    )
    data = parse_output(result)
    internal = check(data, "E299")
    assert result.returncode == 2
    assert data["exitCode"] == 2
    assert internal["messageRu"] == FIXED_INTERNAL_RU
    assert internal["messageEn"] == FIXED_INTERNAL_EN
    combined = result.stdout + result.stderr
    assert str(extension) not in combined
    assert str(continue_home) not in combined
    assert "failure.cmd" not in combined
    assert "Exception" not in combined


def test_all_emitted_codes_are_numeric_e2xx(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory())
    data = parse_output(result)
    assert data["checks"]
    assert all(re.fullmatch(r"E2\d{2}", item["code"]) for item in data["checks"])


def test_secret_canaries_and_paths_never_appear(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    secret = "SUPER_SECRET_CANARY_XYZ123"
    (continue_home / "config.yaml").write_text(
        "name: test\n"
        "models:\n"
        "  - apiKey: ${{ secrets.SUPER_SECRET_CANARY_XYZ123 }}\n"
        "    apiBase: https://user:password@example.invalid/v1?token=CANARY#frag\n",
        encoding="utf-8",
    )
    (continue_home / ".env").write_text(f"SECRET={secret}\n", encoding="utf-8")
    result = run_script(ps_runtime, continue_home, extension_factory())
    combined = result.stdout + result.stderr
    for value in (secret, "password", "CANARY", str(continue_home)):
        assert value not in combined


def test_text_output_redacts_full_paths(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    extension = extension_factory()
    result = run_script(ps_runtime, continue_home, extension, json_mode=False)
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert str(continue_home) not in combined
    assert str(extension) not in combined
    assert "path redacted" in combined


def test_no_writes_inside_continue_home_or_parent(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    write_valid_yaml(continue_home)
    (continue_home / "config.json").write_text("# legacy", encoding="utf-8")
    (continue_home / ".env").write_text("CANARY=unchanged\n", encoding="utf-8")
    extension = extension_factory(root=continue_home.parent / "extension" / "continue.continue-2.0.0")
    before = snapshot_tree(continue_home.parent)
    result = run_script(ps_runtime, continue_home, extension)
    after = snapshot_tree(continue_home.parent)
    assert result.returncode == 0
    assert before == after


def test_four_repository_profiles_are_byte_identical(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
) -> None:
    profiles = {path.name: path.read_bytes() for path in (REPO_ROOT / "configs" / "continue").glob("*.yaml")}
    assert set(profiles) == {
        "hosted-agent.yaml",
        "local-agent.yaml",
        "offline-lite.yaml",
        "online-hybrid.yaml",
    }
    write_valid_yaml(continue_home)
    result = run_script(ps_runtime, continue_home, extension_factory())
    assert result.returncode == 0
    after = {path.name: path.read_bytes() for path in (REPO_ROOT / "configs" / "continue").glob("*.yaml")}
    assert after == profiles


def test_static_input_allowlist_excludes_dotenv_recursion_and_network() -> None:
    """Prove the access boundary from executable source, not only mtimes."""
    source = SCRIPT.read_text(encoding="utf-8-sig")
    executable = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert "$script:AllowedConfigLeafNames = @('config.yaml', 'config.json')" in source
    assert (
        "$script:AllowedExtensionRelativePaths = "
        "@('package.json', 'config-yaml-schema.json', 'dist\\config-yaml-schema.json')"
    ) in source
    assert ".env" not in executable.lower()
    assert not re.search(r"Get-ChildItem[^\n]*ContinueHome", executable, re.IGNORECASE)
    assert "-Recurse" not in executable
    for network_api in ("Invoke-WebRequest", "Invoke-RestMethod", "HttpClient", "WebClient", "https://", "http://"):
        assert network_api.lower() not in executable.lower()


def test_production_docs_have_no_bom_or_mojibake() -> None:
    suspicious = ("вЂ", "в†", "в”", "РЅРµ", "РџР", "РР", "РњР")
    for path in DOCS:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM: {path}"
        text = raw.decode("utf-8")
        for marker in suspicious:
            assert marker not in text, f"Mojibake marker {marker!r}: {path}"


def test_reparse_continue_home_is_rejected_without_reading_target(
    ps_runtime: str,
    tmp_path: Path,
    extension_factory,
) -> None:
    if os.name != "nt":
        pytest.skip("NTFS reparse-point contract")
    target = tmp_path / "target"
    target.mkdir()
    (target / "config.json").write_text("# REPARSE_SECRET_CANARY", encoding="utf-8")
    link = tmp_path / "linked-home"
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        junction = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert junction.returncode == 0, junction.stdout + junction.stderr
    result = run_script(ps_runtime, link, extension_factory())
    data = parse_output(result)
    assert result.returncode == 1
    assert check(data, "E214")["status"] == "FAIL"
    assert "REPARSE_SECRET_CANARY" not in result.stdout + result.stderr


def test_hard_link_input_is_never_modified_or_reflected(
    ps_runtime: str,
    continue_home: Path,
    extension_factory,
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("NTFS hard-link contract")
    external = tmp_path / "external-secret.txt"
    external.write_text("# HARD_LINK_SECRET_CANARY", encoding="utf-8")
    linked_config = continue_home / "config.json"
    try:
        os.link(external, linked_config)
    except OSError as exc:
        pytest.skip(f"Hard-link creation unavailable: {exc}")
    before = external.read_bytes()
    result = run_script(ps_runtime, continue_home, extension_factory())
    assert result.returncode == 1
    assert external.read_bytes() == before
    assert linked_config.read_bytes() == before
    assert "HARD_LINK_SECRET_CANARY" not in result.stdout + result.stderr

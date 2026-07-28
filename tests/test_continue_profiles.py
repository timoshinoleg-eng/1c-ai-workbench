# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Provider-free behavioral tests for the Continue Thin Client profiles.

Covers:
  A. the PowerShell generator (scripts/28_prepare_continue_profile.ps1);
  B. the generated Continue config.yaml structure and the static validator
     (scripts/29_validate_continue_profile.py).

No network, no real API key, no installed Continue/Ollama/Java and no real .hbk
are required. The generator is exercised through subprocess exactly as an
operator would run it.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
GENERATOR = SCRIPTS_DIR / "28_prepare_continue_profile.ps1"
TEMPLATES = ROOT / "configs" / "continue"

sys.path.insert(0, str(SCRIPTS_DIR))
validator = importlib.import_module("29_validate_continue_profile")

FAKE_SECRET = "gsk_FAKE_DO_NOT_LEAK_0123456789abcdef"


def _run_generator(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GENERATOR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """A minimal repo skeleton carrying only the Continue templates."""
    target = tmp_path / "repo"
    (target / "configs" / "continue").mkdir(parents=True)
    for template in TEMPLATES.glob("*.yaml"):
        shutil.copy2(template, target / "configs" / "continue" / template.name)
    rules = target / ".continue" / "rules"
    rules.mkdir(parents=True)
    shutil.copy2(ROOT / ".continue" / "rules" / "1c-workbench.md", rules / "1c-workbench.md")
    shutil.copy2(ROOT / ".continueignore", target / ".continueignore")
    return target


def _output(repo: Path, name: str) -> Path:
    return repo / "generated" / "continue" / name


# ── A. Generator ───────────────────────────────────────────────────────────


def test_generator_online_hybrid_is_deterministic(fake_repo: Path) -> None:
    out_a = _output(fake_repo, "a.yaml")
    out_b = _output(fake_repo, "b.yaml")
    first = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out_a)])
    second = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out_b)])
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert out_a.read_bytes() == out_b.read_bytes()


def test_generator_offline_lite_is_deterministic(fake_repo: Path) -> None:
    out_a = _output(fake_repo, "a.yaml")
    out_b = _output(fake_repo, "b.yaml")
    for out in (out_a, out_b):
        result = _run_generator(["-Profile", "OfflineLite", "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
        assert result.returncode == 0, result.stderr
    assert out_a.read_bytes() == out_b.read_bytes()


def test_generator_check_only_writes_nothing(fake_repo: Path) -> None:
    out = _output(fake_repo, "must-not-appear.yaml")
    before = {path.relative_to(fake_repo): path.read_bytes() for path in fake_repo.rglob("*") if path.is_file()}
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-CheckOnly"])
    assert result.returncode == 0, result.stderr
    assert "Semantic validation: PASS" in result.stdout
    assert not out.exists()
    after = {path.relative_to(fake_repo): path.read_bytes() for path in fake_repo.rglob("*") if path.is_file()}
    assert after == before
    assert not (fake_repo / "generated").exists()


def test_generator_check_only_rejects_semantically_invalid_template(fake_repo: Path) -> None:
    template = fake_repo / "configs" / "continue" / "online-hybrid.yaml"
    data = yaml.safe_load(template.read_text(encoding="utf-8"))
    data["roles"] = ["chat"]
    template.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    out = _output(fake_repo, "must-not-appear.yaml")
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-CheckOnly"])
    assert result.returncode != 0
    assert "top-level 'roles'" in result.stderr
    assert not out.exists()
    assert not (fake_repo / "generated").exists()


def test_generator_refuses_overwrite_without_force(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    first = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
    assert first.returncode == 0, first.stderr
    blocked = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
    assert blocked.returncode != 0
    forced = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-Force"])
    assert forced.returncode == 0, forced.stderr


@pytest.mark.skipif(os.name != "nt", reason="NTFS hard-link behavior")
def test_generator_force_replaces_hard_link_without_touching_external_alias(fake_repo: Path, tmp_path: Path) -> None:
    allowed = fake_repo / "generated" / "continue"
    allowed.mkdir(parents=True)
    outside = tmp_path / "outside.yaml"
    outside.write_bytes(b"external-sentinel")
    linked = allowed / "profile.yaml"
    try:
        os.link(outside, linked)
    except OSError as exc:
        pytest.skip(f"hard-link creation unavailable: {exc}")

    result = _run_generator(["-Profile", "OfflineLite", "-RepoRoot", str(fake_repo), "-OutputPath", str(linked), "-Force"])
    assert result.returncode == 0, result.stderr
    assert outside.read_bytes() == b"external-sentinel"
    assert linked.read_bytes() != b"external-sentinel"
    assert not os.path.samefile(outside, linked)


def test_generator_handles_spaces_and_cyrillic(tmp_path: Path) -> None:
    repo = tmp_path / "репо с пробелом"
    (repo / "configs" / "continue").mkdir(parents=True)
    shutil.copy2(TEMPLATES / "online-hybrid.yaml", repo / "configs" / "continue" / "online-hybrid.yaml")
    rules = repo / ".continue" / "rules"
    rules.mkdir(parents=True)
    shutil.copy2(ROOT / ".continue" / "rules" / "1c-workbench.md", rules / "1c-workbench.md")
    shutil.copy2(ROOT / ".continueignore", repo / ".continueignore")
    out = _output(repo, "out.yaml")
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(repo), "-OutputPath", str(out)])
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    command = {s["name"]: s for s in data["mcpServers"]}["1c-code-index"]["command"]
    assert "репо с пробелом" in command
    assert command.endswith("bsl-indexer.exe")


def test_generator_leaves_no_unresolved_tokens(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
    assert result.returncode == 0, result.stderr
    assert validator.UNRESOLVED_TOKEN.search(out.read_text(encoding="utf-8")) is None


@pytest.mark.parametrize("profile", ["OnlineHybrid", "OfflineLite"])
def test_generator_pins_continue_to_effective_local_ollama_endpoint(fake_repo: Path, profile: str) -> None:
    out = _output(fake_repo, f"{profile}.yaml")
    result = _run_generator(
        ["-Profile", profile, "-RepoRoot", str(fake_repo), "-OutputPath", str(out)],
        env_extra={"OLLAMA_HOST": "127.0.0.1:11534"},
    )
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    ollama = [model for model in data["models"] if model["provider"] == "ollama"]
    assert [model["apiBase"] for model in ollama] == ["http://127.0.0.1:11534"]


def test_generator_rejects_remote_ollama_endpoint_without_writing(fake_repo: Path) -> None:
    out = _output(fake_repo, "must-not-appear.yaml")
    result = _run_generator(
        ["-Profile", "OfflineLite", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-CheckOnly"],
        env_extra={"OLLAMA_HOST": "https://ollama.example.invalid:443"},
    )
    assert result.returncode != 0
    assert "loopback HTTP endpoint" in result.stderr
    assert not out.exists()
    assert not (fake_repo / "generated").exists()


def test_generator_preserves_secret_reference(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
    assert result.returncode == 0, result.stderr
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    groq_keys = {m["apiKey"] for m in data["models"] if m["provider"] == "groq"}
    assert groq_keys == {validator.GROQ_KEY_LITERAL}


def test_generator_does_not_leak_secret_value(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    result = _run_generator(
        ["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-RequireRuntimeReady", "-Force"],
        env_extra={
            "GROQ_API_KEY": FAKE_SECRET,
            "USERPROFILE": str(fake_repo.parent / "isolated-user-profile"),
        },
    )
    # Runtime is incomplete (no indexer/venv/help-db), so the gate fails...
    assert result.returncode != 0
    # ...but the secret value must appear nowhere.
    assert FAKE_SECRET not in result.stdout
    assert FAKE_SECRET not in result.stderr
    assert not out.exists() or FAKE_SECRET not in out.read_text(encoding="utf-8")
    assert "process environment only" in result.stdout


def test_generator_detects_workspace_continue_dotenv_without_printing_value(fake_repo: Path) -> None:
    secret_file = fake_repo / ".continue" / ".env"
    secret_file.write_text(f"GROQ_API_KEY={FAKE_SECRET}\n", encoding="utf-8")
    out = _output(fake_repo, "profile.yaml")
    result = _run_generator(
        ["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-RequireRuntimeReady"]
    )
    assert result.returncode != 0
    assert "configured (workspace .continue/.env)" in result.stdout
    assert FAKE_SECRET not in result.stdout
    assert FAKE_SECRET not in result.stderr
    assert not out.exists()


@pytest.mark.parametrize(
    "dotenv_body",
    [
        'GROQ_API_KEY=""\n',
        "GROQ_API_KEY='   '\n",
        'GROQ_API_KEY="" # disabled\n',
        f"GROQ_API_KEY={FAKE_SECRET}\nGROQ_API_KEY=''\n",
    ],
)
def test_generator_rejects_effectively_empty_continue_dotenv(fake_repo: Path, dotenv_body: str) -> None:
    secret_file = fake_repo / ".continue" / ".env"
    secret_file.write_text(dotenv_body, encoding="utf-8")
    out = _output(fake_repo, "profile.yaml")
    env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    env["USERPROFILE"] = str(fake_repo.parent / "isolated-user-profile")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GENERATOR),
            "-Profile",
            "OnlineHybrid",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(out),
            "-RequireRuntimeReady",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "not configured in Continue dotenv sources" in result.stdout
    assert FAKE_SECRET not in result.stdout
    assert FAKE_SECRET not in result.stderr
    assert not out.exists()


def test_generator_render_only_succeeds_without_runtime(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    # No -RequireRuntimeReady: generation must succeed even though the temp repo
    # has no bsl-indexer.exe, no .venv, no help DB and no GROQ_API_KEY.
    env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GENERATOR),
            "-Profile",
            "OnlineHybrid",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_generator_require_runtime_ready_fails_without_runtime(fake_repo: Path) -> None:
    out = _output(fake_repo, "profile.yaml")
    result = _run_generator(
        ["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out), "-RequireRuntimeReady"]
    )
    assert result.returncode != 0
    assert not out.exists()
    assert "Continue VS Code extension" in result.stdout
    assert "Code MCP handshake/tools-list" in result.stdout
    assert "Help MCP readonly handshake/tools-list" in result.stdout
    assert "Ollama service" in result.stdout


def test_generator_require_runtime_ready_offline_fails_without_ollama(fake_repo: Path, tmp_path: Path) -> None:
    # Resolve the PowerShell executable first, then run it with a PATH that does
    # not contain ollama so the Offline Lite readiness gate must fail.
    pwsh = shutil.which("powershell")
    assert pwsh is not None
    out = _output(fake_repo, "offline.yaml")
    env = {
        "PATH": str(Path(sys.executable).parent),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
        "USERPROFILE": os.environ.get("USERPROFILE", str(tmp_path)),
    }
    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GENERATOR),
            "-Profile",
            "OfflineLite",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(out),
            "-RequireRuntimeReady",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert not out.exists()


def test_generator_rejects_absolute_output_escape_even_with_force(fake_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    result = _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(outside), "-Force"])
    assert result.returncode != 0
    assert "must stay under" in result.stderr
    assert not outside.exists()


def test_generator_rejects_traversal_escape(fake_repo: Path) -> None:
    escaped = fake_repo / "generated" / "escape.yaml"
    result = _run_generator(
        ["-Profile", "OfflineLite", "-RepoRoot", str(fake_repo), "-OutputPath", r"..\escape.yaml", "-Force"]
    )
    assert result.returncode != 0
    assert "must stay under" in result.stderr
    assert not escaped.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_generator_rejects_reparse_directory_escape_even_with_force(fake_repo: Path, tmp_path: Path) -> None:
    allowed = fake_repo / "generated" / "continue"
    allowed.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = allowed / "linked"
    created = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")
    try:
        result = _run_generator(
            [
                "-Profile",
                "OnlineHybrid",
                "-RepoRoot",
                str(fake_repo),
                "-OutputPath",
                str(junction / "profile.yaml"),
                "-Force",
            ]
        )
        assert result.returncode != 0
        assert "reparse point" in result.stderr
        assert not (outside / "profile.yaml").exists()
    finally:
        os.rmdir(junction)


# ── B. Config structure + validator ────────────────────────────────────────


def _generated(fake_repo: Path, profile: str, kind: str) -> Path:
    out = _output(fake_repo, f"{profile}.yaml")
    result = _run_generator(["-Profile", profile, "-RepoRoot", str(fake_repo), "-OutputPath", str(out)])
    assert result.returncode == 0, result.stderr
    assert validator.validate_profile(out, kind, fake_repo) == []
    return out


def test_online_config_roles_are_nested_and_complete(fake_repo: Path) -> None:
    out = _generated(fake_repo, "OnlineHybrid", "online")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "roles" not in data
    groq = [m for m in data["models"] if m["provider"] == "groq"]
    assert len(groq) == 2
    for model in groq:
        assert {"chat", "edit", "apply"}.issubset(set(model["roles"]))
        assert "tool_use" in model["capabilities"]


def test_online_config_has_both_mcp_and_readonly_help(fake_repo: Path) -> None:
    out = _generated(fake_repo, "OnlineHybrid", "online")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    servers = {s["name"]: s for s in data["mcpServers"]}
    assert set(servers) == {"1c-code-index", "1c-help-index"}
    assert servers["1c-help-index"]["env"]["HELP_INDEX_MODE"] == "readonly"


def test_offline_config_has_no_cloud_mcp_or_embed(fake_repo: Path) -> None:
    out = _generated(fake_repo, "OfflineLite", "offline")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data.get("mcpServers") in (None, [])
    roles = {role for m in data["models"] for role in m["roles"]}
    assert roles == {"autocomplete"}
    providers = {m["provider"] for m in data["models"]}
    assert providers == {"ollama"}
    assert all("apiKey" not in m for m in data["models"])
    assert all(m["apiBase"].startswith(("http://127.0.0.1:", "http://localhost:", "http://[::1]:")) for m in data["models"])
    assert "autocomplete only" in data["name"].lower()


def test_configs_have_no_codebase_or_second_rag(fake_repo: Path) -> None:
    for profile, kind in (("OnlineHybrid", "online"), ("OfflineLite", "offline")):
        out = _generated(fake_repo, profile, kind)
        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        canonical = yaml.safe_dump(data, allow_unicode=True).lower()
        assert "@codebase" not in canonical
        for marker in validator.VECTOR_STORE_MARKERS:
            assert marker not in canonical
        assert all("embed" not in m.get("roles", []) for m in data["models"])


def test_validator_accepts_shipped_templates_via_generation(fake_repo: Path) -> None:
    assert validator.validate_profile(_generated(fake_repo, "OnlineHybrid", "online"), "online", fake_repo) == []
    assert validator.validate_profile(_generated(fake_repo, "OfflineLite", "offline"), "offline", fake_repo) == []


@pytest.mark.parametrize(
    ("kind", "mutator", "needle"),
    [
        ("online", lambda d: d.update({"roles": ["chat"]}), "top-level 'roles'"),
        ("online", lambda d: d.update({"schema": "v2"}), "schema must be 'v1'"),
        ("online", lambda d: d["models"][0].update({"apiKey": "gsk_realsecretvalue1234567890"}), "secret"),
        ("online", lambda d: d["models"][0].update({"roles": ["chat", "embed"]}), "embed"),
        (
            "online",
            lambda d: next(s for s in d["mcpServers"] if s["name"] == "1c-help-index").update(
                {"command": "powershell.exe", "args": ["-NoProfile"]}
            ),
            "command must be exactly",
        ),
        (
            "online",
            lambda d: d["mcpServers"].append({"name": "extra", "command": "powershell.exe"}),
            "server names must be exactly",
        ),
        (
            "online",
            lambda d: d["models"].append(
                {"name": "extra", "provider": "ollama", "model": "extra:latest", "roles": ["autocomplete"]}
            ),
            "models must be exactly",
        ),
        ("offline", lambda d: d.update({"mcpServers": [{"name": "x", "command": "y"}]}), "mcpServers"),
        (
            "offline",
            lambda d: d["models"].append({"name": "g", "provider": "groq", "model": "x", "roles": ["chat"]}),
            "ollama",
        ),
        ("offline", lambda d: d["models"][0].update({"model": "definitely-not-qwen:latest"}), "model must be exactly"),
        ("offline", lambda d: d["models"][0].pop("roles"), "roles must be exactly"),
        ("offline", lambda d: d["models"][0].update({"apiBase": "https://ollama.example.invalid"}), "loopback"),
    ],
)
def test_validator_rejects_broken_configs(fake_repo: Path, kind: str, mutator, needle: str) -> None:
    source = fake_repo / "configs" / "continue" / ("online-hybrid.yaml" if kind == "online" else "offline-lite.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    mutator(data)
    bad = fake_repo / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    errors = validator.validate_profile(bad, kind, ROOT)
    assert any(needle.lower() in e.lower() for e in errors), errors


def test_validator_rejects_unresolved_tokens(fake_repo: Path) -> None:
    bad = fake_repo / "unresolved.yaml"
    body = (fake_repo / "configs" / "continue" / "online-hybrid.yaml").read_text(encoding="utf-8")
    bad.write_text(body, encoding="utf-8")  # template still contains {{TOKEN}} placeholders
    errors = validator.validate_profile(bad, "online", ROOT)
    assert any("unresolved" in e for e in errors), errors


def test_rules_and_ignore_files_exist() -> None:
    assert (ROOT / ".continue" / "rules" / "1c-workbench.md").is_file()
    assert (ROOT / ".continueignore").is_file()


def test_bsl_weak_laptop_example_is_valid_and_on_save() -> None:
    import json

    path = ROOT / "configs" / "bsl-language-server.weak-laptop.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["$schema"] == "https://1c-syntax.github.io/bsl-language-server/configuration/schema.json"
    assert data["language"] == "ru"
    # Current BSL LS schema: sendErrors is a string mode; "never" disables telemetry.
    assert data["sendErrors"] == "never"
    diagnostics = data["diagnostics"]
    assert diagnostics["computeTrigger"] == "onSave"
    assert diagnostics["minimumLSPDiagnosticLevel"] == "Warning"
    # traceLog is a log-file path string in the current schema; leaving it unset
    # disables request tracing (the legacy boolean form is no longer the type).
    assert "traceLog" not in data

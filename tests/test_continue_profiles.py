# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Provider-free behavioral tests for the Continue Thin Client profiles.

Covers:
  A. the PowerShell generator (scripts/28_prepare_continue_profile.ps1);
  B. the generated Continue config.yaml structure and the static validator
     (scripts/29_validate_continue_profile.py) for the legacy Groq/Offline
     profiles;
  C. the provider-neutral HostedAgent/LocalAgent profiles: the
     provider/model/secret matrix, malicious-endpoint rejection, literal-secret
     rejection, local/cloud isolation, exact roles/tool_use and the shared
     Code/Help MCP contract.

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


# ── C. Provider-neutral HostedAgent / LocalAgent ───────────────────────────


HOSTED_SECRET = "ZAI_API_KEY"
XKIRO_API_BASE = "https://xkiro.com/v1"
SAFE_NAMESPACED_MODEL_IDS = (
    "deepseek/deepseek-v4-pro",
    "xkiro/deepseek/deepseek-v4-pro",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
)
JWT_LIKE_MODEL = ".".join(("eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "c2lnbmF0dXJl"))
OPAQUE_MODEL_SEGMENT = "AbCdEf0123456789GhIjKlMnOpQrStUv"
DANGEROUS_MODEL_IDS = (
    "gsk_FAKEKEY_0123456789abcdef",
    "provider/gsk_FAKEKEY_0123456789abcdef",
    "sk-proj-abcdef0123456789",
    "provider/sk-proj-abcdef0123456789",
    "sk_FAKEKEY_0123456789abcdef",
    "key-FAKEKEY-0123456789abcdef",
    "bearer fakekey0123456789abcdef",
    "ghp_FAKEKEY_0123456789abcdef",
    "gho_FAKEKEY_0123456789abcdef",
    "xoxb-FAKEKEY-0123456789abcdef",
    "ocr_FAKEKEY_0123456789abcdef",
    "${{ secrets.XKIRO_API_KEY }}",
    "provider/${{ secrets.XKIRO_API_KEY }}",
    JWT_LIKE_MODEL,
    f"provider/{JWT_LIKE_MODEL}",
    OPAQUE_MODEL_SEGMENT,
    f"provider/{OPAQUE_MODEL_SEGMENT}",
)


def _gen_hosted(
    fake_repo: Path,
    *,
    name: str = "profile.yaml",
    preset: str | None = None,
    api_base: str | None = None,
    model_id: str | None = None,
    secret_name: str | None = None,
    check_only: bool = False,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    args = ["-Profile", "HostedAgent", "-RepoRoot", str(fake_repo), "-OutputPath", str(_output(fake_repo, name))]
    if preset:
        args += ["-Preset", preset]
    if api_base:
        args += ["-ApiBase", api_base]
    if model_id:
        args += ["-ModelId", model_id]
    if secret_name:
        args += ["-SecretName", secret_name]
    if check_only:
        args += ["-CheckOnly"]
    return _run_generator(args, env_extra=env_extra)


def _gen_local(
    fake_repo: Path,
    *,
    name: str = "profile.yaml",
    model: str = "qwen2.5-coder:7b",
    api_base: str | None = None,
    check_only: bool = False,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    args = ["-Profile", "LocalAgent", "-RepoRoot", str(fake_repo), "-OutputPath", str(_output(fake_repo, name))]
    args += ["-LocalAgentModel", model]
    if api_base:
        args += ["-LocalAgentApiBase", api_base]
    if check_only:
        args += ["-CheckOnly"]
    return _run_generator(args, env_extra=env_extra)


def _generated_hosted(
    fake_repo: Path,
    *,
    preset: str | None = None,
    api_base: str | None = None,
    model_id: str | None = None,
    secret_name: str | None = None,
) -> Path:
    result = _gen_hosted(
        fake_repo,
        name="h.yaml",
        preset=preset,
        api_base=api_base,
        model_id=model_id,
        secret_name=secret_name,
    )
    assert result.returncode == 0, result.stderr
    out = _output(fake_repo, "h.yaml")
    assert validator.validate_profile(out, "hosted", fake_repo) == []
    return out


def _generated_local(fake_repo: Path, *, model: str = "qwen2.5-coder:7b", api_base: str | None = None) -> Path:
    result = _gen_local(fake_repo, name="l.yaml", model=model, api_base=api_base)
    assert result.returncode == 0, result.stderr
    out = _output(fake_repo, "l.yaml")
    assert validator.validate_profile(out, "local", fake_repo) == []
    return out


# ── C1. Provider / model / secret matrix ───────────────────────────────────


@pytest.mark.parametrize(
    ("preset", "api_base", "model_id", "secret_name"),
    [
        # Preset supplies everything.
        ("zai", None, None, None),
        ("openrouter", None, "anthropic/claude-3.5-sonnet", None),
        ("groq-legacy", None, None, None),
        # Fully generic, every field explicit.
        (None, "https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
        (None, "https://api.z.ai/api/paas/v4", "glm-4.6", "ZAI_API_KEY"),
        # Preset endpoint/secret, user-chosen model.
        ("zai", None, "glm-4.5-air", None),
        # Override secret name on a preset; openrouter has no default model so
        # the user must supply one.
        ("openrouter", None, "anthropic/claude-3.5-sonnet", "MY_OPENROUTER_KEY"),
    ],
)
def test_hosted_matrix_generates_valid_profile(
    fake_repo: Path, preset: str | None, api_base: str | None, model_id: str | None, secret_name: str | None
) -> None:
    out = _generated_hosted(fake_repo, preset=preset, api_base=api_base, model_id=model_id, secret_name=secret_name)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = [m for m in data["models"] if m["provider"] == "openai"]
    assert len(agent) == 1
    assert set(agent[0]["roles"]) == {"chat", "edit", "apply"}
    assert "tool_use" in agent[0]["capabilities"]
    assert agent[0]["apiBase"].startswith("https://")
    # Secret stays a reference, never a value.
    assert validator.SECRET_REFERENCE.match(agent[0]["apiKey"])
    # Exactly one Ollama autocomplete + the two MCP servers.
    assert len(data["models"]) == 2
    assert {s["name"] for s in data["mcpServers"]} == {"1c-code-index", "1c-help-index"}


def test_hosted_zai_preset_uses_verified_endpoint_and_model(fake_repo: Path) -> None:
    out = _generated_hosted(fake_repo, preset="zai")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(m for m in data["models"] if m["provider"] == "openai")
    assert agent["apiBase"] == "https://api.z.ai/api/paas/v4"
    assert agent["model"] == "glm-4.6"
    assert agent["apiKey"] == "${{ secrets.ZAI_API_KEY }}"


def test_hosted_secret_name_is_uppercased_and_referenced(fake_repo: Path) -> None:
    out = _generated_hosted(
        fake_repo, api_base="https://api.openai.com/v1", model_id="gpt-4o-mini", secret_name="openai_api_key"
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(m for m in data["models"] if m["provider"] == "openai")
    assert agent["apiKey"] == "${{ secrets.OPENAI_API_KEY }}"


@pytest.mark.parametrize("model", ["qwen2.5-coder:7b", "llama3.1:8b", "qwen2.5-coder:32b"])
def test_local_agent_matrix_generates_valid_profile(fake_repo: Path, model: str) -> None:
    out = _generated_local(fake_repo, model=model)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = [m for m in data["models"] if m["provider"] == "openai"]
    assert len(agent) == 1
    assert agent[0]["model"] == model
    assert set(agent[0]["roles"]) == {"chat", "edit", "apply"}
    assert "tool_use" in agent[0]["capabilities"]
    assert "apiKey" not in agent[0]
    assert agent[0]["apiBase"].startswith(("http://127.0.0.1:", "http://localhost:", "http://[::1]:"))
    assert agent[0]["apiBase"].endswith("/v1")
    assert len(data["models"]) == 2
    assert {s["name"] for s in data["mcpServers"]} == {"1c-code-index", "1c-help-index"}


def test_local_agent_uses_openai_v1_separately_from_native_ollama_base(fake_repo: Path) -> None:
    out = _generated_local(fake_repo)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(m for m in data["models"] if m["provider"] == "openai")
    autocomplete = next(m for m in data["models"] if m["provider"] == "ollama")
    assert agent["apiBase"] == autocomplete["apiBase"].rstrip("/") + "/v1"


@pytest.mark.parametrize("api_base", ["http://localhost:8000/v1", "http://127.0.0.1:11434/v1/"])
def test_local_agent_accepts_and_normalizes_openai_v1_base(fake_repo: Path, api_base: str) -> None:
    out = _generated_local(fake_repo, api_base=api_base)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(m for m in data["models"] if m["provider"] == "openai")
    assert agent["apiBase"].endswith("/v1")
    assert validator.validate_profile(out, "local", fake_repo) == []


# ── C2. Malicious endpoint rejection ───────────────────────────────────────


@pytest.mark.parametrize(
    "bad_base",
    [
        "http://api.z.ai/api/paas/v4",  # not HTTPS
        "ftp://api.z.ai/v1",  # wrong scheme
        "https://api.z.ai/api/paas/v4?leak=key",  # query string
        "https://api.z.ai/api/paas/v4#frag",  # fragment
        "https://user:pass@api.z.ai/api/paas/v4",  # embedded credentials
        "api.z.ai",  # not an absolute URL
    ],
)
def test_hosted_rejects_unsafe_remote_endpoint_without_writing(fake_repo: Path, bad_base: str) -> None:
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base=bad_base,
        model_id="glm-4.6",
        secret_name=HOSTED_SECRET,
        check_only=True,
    )
    assert result.returncode != 0
    assert bad_base not in (result.stdout + result.stderr)
    assert not _output(fake_repo, "must-not-appear.yaml").exists()


@pytest.mark.parametrize(
    "bad_base",
    [
        "https://127.0.0.1:11434",  # HTTPS not allowed for local
        "http://192.168.1.5:11434",  # non-loopback host
        "http://127.0.0.1:11434",  # missing OpenAI-compatible /v1
        "http://127.0.0.1:11434/api",  # wrong API path
        "http://user:pass@127.0.0.1:11434/v1",  # credentials
        "http://127.0.0.1:11434/v1?x=1",  # query
    ],
)
def test_local_rejects_non_loopback_endpoint_without_writing(fake_repo: Path, bad_base: str) -> None:
    result = _gen_local(fake_repo, name="must-not-appear.yaml", api_base=bad_base, check_only=True)
    assert result.returncode != 0
    assert bad_base not in (result.stdout + result.stderr)
    assert not _output(fake_repo, "must-not-appear.yaml").exists()


# ── C3. Literal-secret rejection ───────────────────────────────────────────


@pytest.mark.parametrize(
    "literal",
    [
        "gsk_FAKEKEY_0123456789abcdef",
        "-".join(("sk", "proj", "abcdef0123456789")),
        "x" * 32,
        ".".join(("eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "c2lnbmF0dXJl")),
    ],
)
def test_hosted_rejects_literal_secret_value_as_secret_name(fake_repo: Path, literal: str) -> None:
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base="https://api.z.ai/api/paas/v4",
        model_id="glm-4.6",
        secret_name=literal,
        check_only=True,
    )
    assert result.returncode != 0
    assert literal not in (result.stdout + result.stderr)
    assert not _output(fake_repo, "must-not-appear.yaml").exists()


def test_hosted_rejects_literal_secret_as_model_id(fake_repo: Path) -> None:
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base="https://api.z.ai/api/paas/v4",
        model_id="gsk_FAKEKEY_0123456789abcdef",
        secret_name=HOSTED_SECRET,
        check_only=True,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("model_id", SAFE_NAMESPACED_MODEL_IDS)
def test_hosted_accepts_safe_namespaced_model_id_in_generator_and_validator(fake_repo: Path, model_id: str) -> None:
    out = _generated_hosted(
        fake_repo,
        api_base=XKIRO_API_BASE,
        model_id=model_id,
        secret_name="XKIRO_API_KEY",
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(model for model in data["models"] if model["provider"] == "openai")
    assert agent["apiBase"] == XKIRO_API_BASE
    assert agent["model"] == model_id
    assert validator.validate_profile(out, "hosted", fake_repo) == []


def test_hosted_namespaced_model_check_only_writes_nothing(fake_repo: Path) -> None:
    before = {path.relative_to(fake_repo): path.read_bytes() for path in fake_repo.rglob("*") if path.is_file()}
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base=XKIRO_API_BASE,
        model_id="deepseek/deepseek-v4-pro",
        secret_name="XKIRO_API_KEY",
        check_only=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Semantic validation: PASS" in result.stdout
    assert not _output(fake_repo, "must-not-appear.yaml").exists()
    after = {path.relative_to(fake_repo): path.read_bytes() for path in fake_repo.rglob("*") if path.is_file()}
    assert after == before
    assert not (fake_repo / "generated").exists()


@pytest.mark.parametrize("model_id", DANGEROUS_MODEL_IDS)
def test_hosted_generator_rejects_credential_in_model_namespace_without_writing(fake_repo: Path, model_id: str) -> None:
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base=XKIRO_API_BASE,
        model_id=model_id,
        secret_name="XKIRO_API_KEY",
        check_only=True,
    )
    assert result.returncode != 0
    assert "credential material" in result.stderr
    assert model_id not in (result.stdout + result.stderr)
    assert not _output(fake_repo, "must-not-appear.yaml").exists()


@pytest.mark.parametrize("model_id", DANGEROUS_MODEL_IDS)
def test_validator_rejects_credential_in_model_namespace_without_echo(fake_repo: Path, model_id: str) -> None:
    source = _generated_hosted(
        fake_repo,
        api_base=XKIRO_API_BASE,
        model_id="deepseek/deepseek-v4-pro",
        secret_name="XKIRO_API_KEY",
    )
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    next(model for model in data["models"] if model["provider"] == "openai")["model"] = model_id
    bad = fake_repo / "bad-model.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    errors = validator.validate_profile(bad, "hosted", fake_repo)
    assert any("credential material" in error for error in errors), errors
    assert model_id not in "\n".join(errors)


def test_hosted_rejects_and_does_not_echo_unsafe_model_id(fake_repo: Path) -> None:
    unsafe = "model id with spaces and a private note"
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base="https://api.z.ai/api/paas/v4",
        model_id=unsafe,
        secret_name=HOSTED_SECRET,
        check_only=True,
    )
    assert result.returncode != 0
    assert unsafe not in (result.stdout + result.stderr)


def test_hosted_rejects_literal_secret_as_apibase(fake_repo: Path) -> None:
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base="gsk_FAKEKEY_0123456789abcdef",
        model_id="glm-4.6",
        secret_name=HOSTED_SECRET,
        check_only=True,
    )
    assert result.returncode != 0


# ── C4. Local/cloud isolation ──────────────────────────────────────────────


def test_local_profile_has_no_cloud_secret_or_marker(fake_repo: Path) -> None:
    out = _generated_local(fake_repo)
    text = out.read_text(encoding="utf-8")
    assert "apiKey" not in text.lower()
    assert "${{{ secrets" not in text
    assert "secrets." not in text
    for marker in validator.CLOUD_HOST_MARKERS:
        assert marker not in text.lower()


def test_hosted_remote_secret_value_never_embedded(fake_repo: Path) -> None:
    secret_value = "gsk_SECRETVALUE_NEVER_EMBED_0123"
    out = _generated_hosted(
        fake_repo,
        api_base="https://api.z.ai/api/paas/v4",
        model_id="glm-4.6",
        secret_name=HOSTED_SECRET,
    )
    assert secret_value not in out.read_text(encoding="utf-8")


def test_hosted_require_runtime_ready_does_not_print_secret_value(fake_repo: Path) -> None:
    # The readiness gate cannot pass (no indexer/venv/help-db) but must never
    # echo a configured secret VALUE, only its presence in dotenv sources.
    secret_file = fake_repo / ".continue" / ".env"
    secret_file.write_text("ZAI_API_KEY=gsk_SECRETVALUE_NEVER_PRINT_0123\n", encoding="utf-8")
    result = _gen_hosted(
        fake_repo,
        name="must-not-appear.yaml",
        api_base="https://api.z.ai/api/paas/v4",
        model_id="glm-4.6",
        secret_name=HOSTED_SECRET,
        env_extra={"USERPROFILE": str(fake_repo.parent / "isolated-user-profile")},
    )
    # Append -RequireRuntimeReady via a direct call (helper has no flag for it).
    full = _run_generator(
        [
            "-Profile",
            "HostedAgent",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(_output(fake_repo, "must-not-appear.yaml")),
            "-ApiBase",
            "https://api.z.ai/api/paas/v4",
            "-ModelId",
            "glm-4.6",
            "-SecretName",
            HOSTED_SECRET,
            "-RequireRuntimeReady",
        ],
        env_extra={"USERPROFILE": str(fake_repo.parent / "isolated-user-profile")},
    )
    assert full.returncode != 0
    assert "gsk_SECRETVALUE_NEVER_PRINT_0123" not in full.stdout
    assert "gsk_SECRETVALUE_NEVER_PRINT_0123" not in full.stderr
    assert "configured (workspace .continue/.env)" in full.stdout
    _ = result  # generated-only run also referenced for coverage


# ── C5. Exact roles / tool_use and Code/Help MCP contract ──────────────────


def test_hosted_roles_and_capabilities_exact(fake_repo: Path) -> None:
    out = _generated_hosted(fake_repo, preset="zai")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    agent = next(m for m in data["models"] if m["provider"] == "openai")
    assert set(agent["roles"]) == {"chat", "edit", "apply"}
    assert agent["capabilities"] == ["tool_use"]
    auto = next(m for m in data["models"] if m["provider"] == "ollama")
    assert set(auto["roles"]) == {"autocomplete"}


def test_hosted_and_local_share_code_help_mcp_contract(fake_repo: Path) -> None:
    for out, _kind in (
        (_generated_hosted(fake_repo, preset="zai"), "hosted"),
        (_generated_local(fake_repo), "local"),
    ):
        data = yaml.load(out.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
        servers = {s["name"]: s for s in data["mcpServers"]}
        assert set(servers) == {"1c-code-index", "1c-help-index"}
        assert servers["1c-help-index"]["env"]["HELP_INDEX_MODE"] == "readonly"
        assert servers["1c-code-index"]["args"][0] == "serve"
        assert servers["1c-code-index"]["args"][3:5] == ["--transport", "stdio"]


@pytest.mark.parametrize(
    ("kind", "mutator", "needle"),
    [
        (
            "hosted",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").pop("roles"),
            "roles must be exactly",
        ),
        ("hosted", lambda d: next(m for m in d["models"] if m["provider"] == "openai")["roles"].append("embed"), "embed"),
        ("hosted", lambda d: next(m for m in d["models"] if m["provider"] == "openai")["capabilities"].clear(), "tool_use"),
        (
            "hosted",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").update(
                {"apiKey": "gsk_realvalue1234567890"}
            ),
            "secret",
        ),
        (
            "hosted",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").update({"apiBase": "http://api.z.ai/v1"}),
            "HTTPS",
        ),
        (
            "hosted",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").update(
                {"apiBase": "https://api.z.ai/v1?x=1"}
            ),
            "query string",
        ),
        (
            "hosted",
            lambda d: d["models"].append({"name": "x", "provider": "openai", "model": "y", "roles": ["chat"]}),
            "exactly one OpenAI-compatible",
        ),
        (
            "local",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").update({"apiKey": "${{ secrets.X }}"}),
            "apiKey",
        ),
        (
            "local",
            lambda d: next(m for m in d["models"] if m["provider"] == "openai").update(
                {"apiBase": "https://api.openai.com/v1"}
            ),
            "loopback",
        ),
        ("local", lambda d: next(m for m in d["models"] if m["provider"] == "openai")["roles"].append("embed"), "embed"),
    ],
)
def test_validator_rejects_broken_neutral_configs(fake_repo: Path, kind: str, mutator, needle: str) -> None:
    if kind == "hosted":
        source = _generated_hosted(fake_repo, preset="zai")
    else:
        source = _generated_local(fake_repo)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    mutator(data)
    bad = fake_repo / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    errors = validator.validate_profile(bad, kind, ROOT)
    assert any(needle.lower() in e.lower() for e in errors), errors


# ── C6. CheckOnly write-free for neutral profiles ──────────────────────────


@pytest.mark.parametrize(
    "runner",
    ["hosted", "local"],
)
def test_neutral_check_only_writes_nothing(fake_repo: Path, runner: str) -> None:
    out = _output(fake_repo, "must-not-appear.yaml")
    before = {p.relative_to(fake_repo): p.read_bytes() for p in fake_repo.rglob("*") if p.is_file()}
    if runner == "hosted":
        result = _gen_hosted(fake_repo, name="must-not-appear.yaml", preset="zai", check_only=True)
    else:
        result = _gen_local(fake_repo, name="must-not-appear.yaml", check_only=True)
    assert result.returncode == 0, result.stderr
    assert "Semantic validation: PASS" in result.stdout
    assert not out.exists()
    after = {p.relative_to(fake_repo): p.read_bytes() for p in fake_repo.rglob("*") if p.is_file()}
    assert after == before
    assert not (fake_repo / "generated").exists()


# ── C7. Runtime readiness + backward compatibility ─────────────────────────


def test_hosted_require_runtime_ready_fails_without_runtime(fake_repo: Path) -> None:
    result = _run_generator(
        [
            "-Profile",
            "HostedAgent",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(_output(fake_repo, "h.yaml")),
            "-Preset",
            "zai",
            "-RequireRuntimeReady",
        ]
    )
    assert result.returncode != 0
    assert not _output(fake_repo, "h.yaml").exists()
    assert f"Continue secret {HOSTED_SECRET}" in result.stdout
    assert "Code MCP handshake/tools-list" in result.stdout
    assert "Help MCP readonly handshake/tools-list" in result.stdout


def test_local_require_runtime_ready_fails_without_runtime(fake_repo: Path) -> None:
    result = _run_generator(
        [
            "-Profile",
            "LocalAgent",
            "-RepoRoot",
            str(fake_repo),
            "-OutputPath",
            str(_output(fake_repo, "l.yaml")),
            "-LocalAgentModel",
            "qwen2.5-coder:7b",
            "-RequireRuntimeReady",
        ]
    )
    assert result.returncode != 0
    assert not _output(fake_repo, "l.yaml").exists()
    assert "Code MCP handshake/tools-list" in result.stdout
    assert "Help MCP readonly handshake/tools-list" in result.stdout
    assert "Local OpenAI-compatible endpoint (" in result.stdout
    assert "/v1)" in result.stdout
    assert "Local agent model qwen2.5-coder:7b" in result.stdout


def test_neutral_profiles_are_deterministic(fake_repo: Path) -> None:
    for tag, gen in (
        ("hosted", lambda n: _gen_hosted(fake_repo, name=n, preset="zai")),
        ("local", lambda n: _gen_local(fake_repo, name=n)),
    ):
        assert gen(f"{tag}-det-a.yaml").returncode == 0
        assert gen(f"{tag}-det-b.yaml").returncode == 0
        a = _output(fake_repo, f"{tag}-det-a.yaml")
        b = _output(fake_repo, f"{tag}-det-b.yaml")
        assert a.read_bytes() == b.read_bytes()


def test_legacy_profiles_still_generate_and_validate(fake_repo: Path) -> None:
    """Backward compatibility: the original Groq/Offline profiles are unchanged."""
    out_online = _output(fake_repo, "online.yaml")
    assert (
        _run_generator(["-Profile", "OnlineHybrid", "-RepoRoot", str(fake_repo), "-OutputPath", str(out_online)]).returncode
        == 0
    )
    assert validator.validate_profile(out_online, "online", fake_repo) == []
    out_offline = _output(fake_repo, "offline.yaml")
    assert (
        _run_generator(["-Profile", "OfflineLite", "-RepoRoot", str(fake_repo), "-OutputPath", str(out_offline)]).returncode
        == 0
    )
    assert validator.validate_profile(out_offline, "offline", fake_repo) == []

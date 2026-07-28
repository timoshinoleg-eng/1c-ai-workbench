"""Static validator for generated 1C AI Workbench Continue config.yaml profiles.

Parses the YAML for real (not string presence) and enforces the Thin Client AI
contracts:

* schema v1, well-formed ``models`` with roles nested inside each model;
* no top-level ``roles``; only Continue-recognized roles;
* the Groq key is exactly the Continue secret reference, never a real secret;
* no unresolved path placeholders, no ``@Codebase``/deprecated fields;
* no embed models and no vector-store configuration (LanceDB/Transformers.js/Nomic);
* Online Hybrid exposes both local MCP servers with ``HELP_INDEX_MODE=readonly``;
* Offline Lite has no cloud provider, no MCP, no secrets and autocomplete only;
* the workspace ships ``.continue/rules/1c-workbench.md`` and a root ``.continueignore``.

Exit code is non-zero when any check fails.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

SECRET_REFERENCE = re.compile(r"^\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}$")
GROQ_KEY_LITERAL = "${{ secrets.GROQ_API_KEY }}"
UNRESOLVED_TOKEN = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
# Recognized Continue v1 model roles.
ALLOWED_ROLES = {"chat", "autocomplete", "embed", "rerank", "edit", "apply", "summarize"}
CLOUD_PROVIDERS = {"groq", "openai", "anthropic", "mistral", "deepseek", "azure", "gemini", "google"}
VECTOR_STORE_MARKERS = ("lancedb", "transformers.js", "nomic")
REQUIRED_GROQ_MODELS = {"openai/gpt-oss-120b", "qwen/qwen3.6-27b"}
OLLAMA_AUTOCOMPLETE_MODEL = "qwen2.5-coder:1.5b-base"


def _looks_like_real_secret(value: str) -> bool:
    """Heuristics for a pasted real credential (not a ${{ secrets.* }} reference)."""
    if SECRET_REFERENCE.match(value):
        return False
    prefixes = ("gsk_", "sk-", "sk_", "key-", "bearer ", "ghp_", "gho_", "xox")
    lowered = value.strip().lower()
    if any(lowered.startswith(prefix) for prefix in prefixes):
        return True
    compact = value.strip()
    if len(compact) >= 24 and re.fullmatch(r"[A-Za-z0-9+/=_\-]{24,}", compact) is not None:
        return True
    return len(compact) >= 24 and re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", compact) is not None


def _model_roles(model: dict[str, Any]) -> list[str]:
    roles = model.get("roles")
    if roles is None:
        return []
    if not isinstance(roles, list):
        return [str(roles)]
    return [str(role) for role in roles]


def _same_path(actual: object, expected: Path) -> bool:
    if not isinstance(actual, str) or not actual:
        return False
    return os.path.normcase(os.path.abspath(actual)) == os.path.normcase(os.path.abspath(expected))


def _validate_local_ollama_endpoint(model: dict[str, Any], errors: list[str]) -> None:
    value = model.get("apiBase")
    label = f"Ollama model {model.get('model')!r}"
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must declare an explicit local apiBase")
        return
    _assert_loopback_http(value, label, errors)


def _assert_loopback_http(value: str, label: str, errors: list[str]) -> None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        errors.append(f"{label} apiBase must be a valid local HTTP URL")
        return
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        errors.append(f"{label} apiBase must be an explicit loopback HTTP endpoint")


def _assert_loopback_openai_base(value: str, label: str, errors: list[str]) -> None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        errors.append(f"{label} apiBase must be a valid loopback OpenAI-compatible URL")
        return
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("/v1", "/v1/")
        or parsed.query
        or parsed.fragment
    ):
        errors.append(f"{label} apiBase must be an explicit loopback HTTP endpoint ending in /v1")


def _assert_https_remote(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must declare an HTTPS apiBase")
        return
    try:
        parsed = urlsplit(value)
    except ValueError:
        errors.append(f"{label} apiBase must be a valid HTTPS URL")
        return
    if parsed.scheme != "https":
        errors.append(f"{label} apiBase must use HTTPS, got scheme {parsed.scheme!r}")
    if not parsed.hostname:
        errors.append(f"{label} apiBase must include a host")
    if parsed.username is not None or parsed.password is not None:
        errors.append(f"{label} apiBase must not embed credentials")
    if parsed.query:
        errors.append(f"{label} apiBase must not contain a query string")
    if parsed.fragment:
        errors.append(f"{label} apiBase must not contain a fragment")


SECRET_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
# Cloud host markers that must never appear in a fully-local (LocalAgent/Offline)
# profile. A path-bearing https URL like https://api.openai.com/v1 reduces to the
# host marker api.openai.com.
CLOUD_HOST_MARKERS = (
    "api.groq.com",
    "api.openai.com",
    "openrouter.ai",
    "api.anthropic.com",
    "api.mistral.ai",
    "api.deepseek.com",
    "generativelanguage.googleapis.com",
    "api.z.ai",
)


def _references_any_secret(canonical: str) -> bool:
    return "${{ secrets" in canonical or "secrets." in canonical


def _mentions_cloud_host(canonical: str) -> str | None:
    lowered = canonical.lower()
    for marker in CLOUD_HOST_MARKERS:
        if marker in lowered:
            return marker
    return None


def _common_checks(data: dict[str, Any], canonical: str, errors: list[str]) -> None:
    if data.get("schema") != "v1":
        errors.append(f"schema must be 'v1', got {data.get('schema')!r}")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        errors.append("top-level 'name' is required")
    if "version" not in data:
        errors.append("top-level 'version' is required")
    if "roles" in data:
        errors.append("top-level 'roles' is forbidden; roles must be nested inside each model")
    if "tabAutocompleteModel" in data:
        errors.append("deprecated top-level 'tabAutocompleteModel' is forbidden in schema v1")

    # Marker checks run on the parsed-and-re-dumped config so documentation
    # comments that merely mention a forbidden feature do not cause false positives.
    if "@Codebase" in canonical:
        errors.append("deprecated '@Codebase' context is forbidden")
    for context in data.get("context") or []:
        if isinstance(context, dict) and str(context.get("provider")).lower() == "codebase":
            errors.append("deprecated 'codebase' context provider is forbidden")

    lowered = canonical.lower()
    for marker in VECTOR_STORE_MARKERS:
        if marker in lowered:
            errors.append(f"vector-store configuration is forbidden (found {marker!r})")

    models = data.get("models")
    if not isinstance(models, list) or not models:
        errors.append("'models' must be a non-empty list")
        return

    for index, model in enumerate(models):
        label = f"models[{index}]"
        if not isinstance(model, dict):
            errors.append(f"{label} must be a mapping")
            continue
        for required in ("name", "provider", "model"):
            if not isinstance(model.get(required), str) or not model[required].strip():
                errors.append(f"{label}.{required} is required")
        model_id = model.get("model")
        if isinstance(model_id, str) and model_id and not MODEL_ID_PATTERN.fullmatch(model_id):
            errors.append(f"{label}.model contains unsupported characters or exceeds 200 characters")
        if isinstance(model_id, str) and _looks_like_real_secret(model_id):
            errors.append(f"{label}.model looks like credential material; use a model identifier")
        roles = _model_roles(model)
        for role in roles:
            if role not in ALLOWED_ROLES:
                errors.append(f"{label} has unrecognized role {role!r}")
        if "embed" in roles:
            errors.append(f"{label} must not use the 'embed' role")
        if "embedOptions" in model:
            errors.append(f"{label} must not define embedOptions")
        api_key = model.get("apiKey")
        if api_key is not None:
            if not isinstance(api_key, str):
                errors.append(f"{label}.apiKey must be a string")
            elif not SECRET_REFERENCE.match(api_key):
                if _looks_like_real_secret(api_key):
                    errors.append(f"{label}.apiKey looks like a real secret; use a ${{{{ secrets.* }}}} reference")
                else:
                    errors.append(f"{label}.apiKey must be a ${{{{ secrets.* }}}} reference")


def _online_checks(data: dict[str, Any], errors: list[str], repo_root: Path) -> None:
    models = data.get("models") or []
    groq_models = [m for m in models if isinstance(m, dict) and m.get("provider") == "groq"]
    groq_model_ids = [str(m.get("model")) for m in groq_models]
    if len(groq_models) != 2 or set(groq_model_ids) != REQUIRED_GROQ_MODELS or len(set(groq_model_ids)) != 2:
        errors.append(f"Online Hybrid Groq models must be exactly {sorted(REQUIRED_GROQ_MODELS)}")

    for model in groq_models:
        label = f"groq model {model.get('model')!r}"
        roles = set(_model_roles(model))
        if roles != {"chat", "edit", "apply"}:
            errors.append(f"{label} roles must be exactly chat/edit/apply, got {sorted(roles)}")
        if model.get("apiKey") != GROQ_KEY_LITERAL:
            errors.append(f"{label} apiKey must be exactly {GROQ_KEY_LITERAL!r}")
        capabilities = model.get("capabilities") or []
        if "tool_use" not in [str(c) for c in capabilities]:
            errors.append(f"{label} should declare the 'tool_use' capability for Agent-mode MCP access")

    ollama = [m for m in models if isinstance(m, dict) and m.get("provider") == "ollama"]
    autocomplete = [m for m in ollama if str(m.get("model")) == OLLAMA_AUTOCOMPLETE_MODEL]
    if len(models) != 3 or len(ollama) != 1 or len(autocomplete) != 1:
        errors.append(
            "Online Hybrid models must be exactly two required Groq models and "
            f"one Ollama {OLLAMA_AUTOCOMPLETE_MODEL!r} model"
        )
    for model in autocomplete:
        if set(_model_roles(model)) != {"autocomplete"}:
            errors.append(f"Ollama model {OLLAMA_AUTOCOMPLETE_MODEL!r} must have only the autocomplete role")
        _validate_local_ollama_endpoint(model, errors)

    _shared_mcp_checks(data, errors, repo_root, profile_label="Online Hybrid")


def _shared_mcp_checks(data: dict[str, Any], errors: list[str], repo_root: Path, profile_label: str) -> None:
    """Exact Code MCP + readonly Help MCP contract shared by online/hosted/local."""
    servers = data.get("mcpServers") or []
    server_names = [str(s.get("name")) for s in servers if isinstance(s, dict)]
    required_servers = {"1c-code-index", "1c-help-index"}
    if len(servers) != 2 or len(server_names) != 2 or set(server_names) != required_servers:
        errors.append(f"{profile_label} MCP server names must be exactly {sorted(required_servers)} with no duplicates")

    by_name = {str(s.get("name")): s for s in servers if isinstance(s, dict)}
    code = by_name.get("1c-code-index")
    if code is not None:
        args = [str(a) for a in (code.get("args") or [])]
        expected_command = repo_root / "tools" / "code-index-mcp" / "target" / "release" / "bsl-indexer.exe"
        expected_source = repo_root / "generated" / "index" / "source-mirror"
        expected_home = repo_root / "generated" / "code-index-home"
        if not _same_path(code.get("command"), expected_command):
            errors.append(f"1c-code-index command must be exactly repo-local {expected_command}")
        if len(args) != 5 or args[:2] != ["serve", "--path"] or args[3:] != ["--transport", "stdio"]:
            errors.append("1c-code-index args must be exactly 'serve --path onec=<source-mirror> --transport stdio'")
        elif not args[2].startswith("onec=") or not _same_path(args[2][len("onec=") :], expected_source):
            errors.append(f"1c-code-index source mirror must be exactly repo-local {expected_source}")
        code_env = code.get("env") or {}
        if set(code_env) != {"CODE_INDEX_HOME"} or not _same_path(code_env.get("CODE_INDEX_HOME"), expected_home):
            errors.append(f"1c-code-index env must set only repo-local CODE_INDEX_HOME={expected_home}")

    help_server = by_name.get("1c-help-index")
    if help_server is not None:
        expected_python = repo_root / ".venv" / "Scripts" / "python.exe"
        expected_server = repo_root / "tools" / "help-index-mcp" / "server.py"
        help_args = help_server.get("args") or []
        env = help_server.get("env") or {}
        if not _same_path(help_server.get("command"), expected_python):
            errors.append(f"1c-help-index command must be exactly repo-local {expected_python}")
        if len(help_args) != 1 or not _same_path(help_args[0], expected_server):
            errors.append(f"1c-help-index args must contain only repo-local {expected_server}")
        if set(env) != {"HELP_INDEX_MODE", "WORKBENCH_ROOT"}:
            errors.append("1c-help-index env must contain only HELP_INDEX_MODE and WORKBENCH_ROOT")
        if env.get("HELP_INDEX_MODE") != "readonly":
            errors.append("1c-help-index env must set HELP_INDEX_MODE=readonly")
        if not _same_path(env.get("WORKBENCH_ROOT"), repo_root):
            errors.append(f"1c-help-index WORKBENCH_ROOT must be exactly {repo_root}")


def _hosted_checks(data: dict[str, Any], canonical: str, errors: list[str], repo_root: Path) -> None:
    """Provider-neutral hosted agent: one OpenAI-compatible HTTPS model + Ollama."""
    models = data.get("models") or []
    agent_models = [m for m in models if isinstance(m, dict) and str(m.get("provider")).lower() == "openai"]
    if len(agent_models) != 1:
        errors.append("Hosted Agent must define exactly one OpenAI-compatible (provider 'openai') agent model")
    for model in agent_models:
        label = "hosted agent model"
        roles = set(_model_roles(model))
        if roles != {"chat", "edit", "apply"}:
            errors.append(f"{label} roles must be exactly chat/edit/apply, got {sorted(roles)}")
        capabilities = [str(c) for c in (model.get("capabilities") or [])]
        if "tool_use" not in capabilities:
            errors.append(f"{label} must declare the 'tool_use' capability for Agent-mode MCP access")
        api_key = model.get("apiKey")
        if not isinstance(api_key, str) or not SECRET_REFERENCE.match(api_key):
            if isinstance(api_key, str) and _looks_like_real_secret(api_key):
                errors.append(f"{label} apiKey looks like a real secret; use a ${{{{ secrets.* }}}} reference")
            else:
                errors.append(f"{label} apiKey must be a ${{{{ secrets.* }}}} reference")
        else:
            inner = re.search(r"secrets\.([A-Za-z0-9_]+)", api_key)
            if inner and not SECRET_NAME_PATTERN.match(inner.group(1)):
                errors.append(f"{label} secret name must be UPPER_SNAKE_CASE")
        _assert_https_remote(model.get("apiBase"), label, errors)

    ollama = [m for m in models if isinstance(m, dict) and m.get("provider") == "ollama"]
    autocomplete = [m for m in ollama if str(m.get("model")) == OLLAMA_AUTOCOMPLETE_MODEL]
    if len(models) != 2 or len(ollama) != 1 or len(autocomplete) != 1 or len(agent_models) != 1:
        errors.append(
            "Hosted Agent models must be exactly one OpenAI-compatible agent model and "
            f"one Ollama {OLLAMA_AUTOCOMPLETE_MODEL!r} autocomplete model"
        )
    for model in autocomplete:
        if set(_model_roles(model)) != {"autocomplete"}:
            errors.append(f"Ollama model {OLLAMA_AUTOCOMPLETE_MODEL!r} must have only the autocomplete role")
        _validate_local_ollama_endpoint(model, errors)

    _shared_mcp_checks(data, errors, repo_root, profile_label="Hosted Agent")


def _local_checks(data: dict[str, Any], canonical: str, errors: list[str], repo_root: Path) -> None:
    """Provider-neutral local agent: one loopback tool-capable model + Ollama, no cloud."""
    # A fully-local profile must never reference a secret, an apiKey or a cloud host.
    if _references_any_secret(canonical):
        errors.append("Local Agent must not reference any secret")
    if "apikey" in canonical.lower():
        errors.append("Local Agent must not contain any apiKey")
    cloud = _mentions_cloud_host(canonical)
    if cloud is not None:
        errors.append(f"Local Agent must not contain a cloud API URL ({cloud})")

    models = data.get("models") or []
    # The local agent model is OpenAI-compatible (provider 'openai') on loopback.
    agent_models = [
        m
        for m in models
        if isinstance(m, dict) and str(m.get("provider")).lower() == "openai" and "autocomplete" not in _model_roles(m)
    ]
    ollama = [m for m in models if isinstance(m, dict) and m.get("provider") == "ollama"]
    autocomplete = [m for m in ollama if str(m.get("model")) == OLLAMA_AUTOCOMPLETE_MODEL]
    if len(agent_models) != 1:
        errors.append("Local Agent must define exactly one local OpenAI-compatible (provider 'openai') agent model")
    if len(models) != 2 or len(ollama) != 1 or len(autocomplete) != 1:
        errors.append(
            "Local Agent models must be exactly one local agent model and "
            f"one Ollama {OLLAMA_AUTOCOMPLETE_MODEL!r} autocomplete model"
        )
    for model in agent_models:
        label = "local agent model"
        roles = set(_model_roles(model))
        if roles != {"chat", "edit", "apply"}:
            errors.append(f"{label} roles must be exactly chat/edit/apply, got {sorted(roles)}")
        capabilities = [str(c) for c in (model.get("capabilities") or [])]
        if "tool_use" not in capabilities:
            errors.append(f"{label} must declare the 'tool_use' capability for Agent-mode MCP access")
        if "apiKey" in model:
            errors.append(f"{label} must not declare an apiKey (local profile carries no secret)")
        _assert_loopback_openai_base(model.get("apiBase"), label, errors)
    for model in autocomplete:
        if set(_model_roles(model)) != {"autocomplete"}:
            errors.append(f"Ollama model {OLLAMA_AUTOCOMPLETE_MODEL!r} must have only the autocomplete role")
        _validate_local_ollama_endpoint(model, errors)

    _shared_mcp_checks(data, errors, repo_root, profile_label="Local Agent")


def _offline_checks(data: dict[str, Any], canonical: str, errors: list[str]) -> None:
    if data.get("mcpServers"):
        errors.append("Offline Lite must not define mcpServers")

    # Run on the parsed-and-re-dumped config so comments documenting the absence
    # of cloud features do not trip the checks.
    lowered = canonical.lower()
    if "${{ secrets" in canonical or "secrets." in canonical:
        errors.append("Offline Lite must not reference any secret")
    if "apikey" in lowered:
        errors.append("Offline Lite must not contain any apiKey")
    for url_marker in ("api.groq.com", "api.openai.com", "https://api."):
        if url_marker in lowered:
            errors.append(f"Offline Lite must not contain a cloud API URL ({url_marker})")

    models = data.get("models") or []
    if len(models) != 1:
        errors.append("Offline Lite must define exactly one Ollama autocomplete model")
    for model in models:
        if not isinstance(model, dict):
            continue
        provider = str(model.get("provider")).lower()
        if provider in CLOUD_PROVIDERS or provider != "ollama":
            errors.append(f"Offline Lite allows only the ollama provider, got {provider!r}")
        if model.get("model") != OLLAMA_AUTOCOMPLETE_MODEL:
            errors.append(f"Offline Lite model must be exactly {OLLAMA_AUTOCOMPLETE_MODEL!r}")
        _validate_local_ollama_endpoint(model, errors)
        roles = set(_model_roles(model))
        if roles != {"autocomplete"}:
            errors.append(f"Offline Lite model roles must be exactly autocomplete, got {sorted(roles)}")

    name = str(data.get("name") or "")
    if "autocomplete only" not in name.lower():
        errors.append("Offline Lite name must state 'autocomplete only'")


def validate_profile_text(raw: str, kind: str, repo_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]
    if not isinstance(data, dict):
        return ["top-level YAML must be a mapping"]

    # Unresolved placeholders are checked on the file exactly as written.
    if UNRESOLVED_TOKEN.search(raw):
        errors.append(f"unresolved path placeholder(s): {UNRESOLVED_TOKEN.findall(raw)}")

    # Structural marker checks use the parsed-and-re-dumped config (no comments).
    canonical = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    _common_checks(data, canonical, errors)
    if kind == "online":
        _online_checks(data, errors, repo_root)
    elif kind == "hosted":
        _hosted_checks(data, canonical, errors, repo_root)
    elif kind == "local":
        _local_checks(data, canonical, errors, repo_root)
    elif kind == "offline":
        _offline_checks(data, canonical, errors)
    else:
        errors.append(f"unknown profile kind: {kind!r}")

    rules_file = repo_root / ".continue" / "rules" / "1c-workbench.md"
    if not rules_file.is_file():
        errors.append(f"missing Continue rules file: {rules_file}")
    ignore_file = repo_root / ".continueignore"
    if not ignore_file.is_file():
        errors.append(f"missing root .continueignore: {ignore_file}")

    return errors


def validate_profile(config_path: Path, kind: str, repo_root: Path) -> list[str]:
    if not config_path.is_file():
        return [f"config file not found: {config_path}"]
    return validate_profile_text(config_path.read_text(encoding="utf-8"), kind, repo_root)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate generated Continue Thin Client profiles.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Generated config.yaml to validate")
    source.add_argument(
        "--stdin",
        action="store_true",
        help="Read rendered config.yaml from stdin (semantic validation without a temporary file)",
    )
    source.add_argument(
        "--stdin-base64",
        help="Decode rendered UTF-8 config.yaml from base64 (PowerShell 5.1-safe in-memory validation)",
    )
    parser.add_argument(
        "--kind",
        choices=("online", "hosted", "local", "offline"),
        required=True,
        help="Expected profile kind",
    )
    parser.add_argument("--repo-root", type=Path, default=root, help="Workbench root for rules/ignore checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stdin:
        config_label = "<stdin>"
        raw = sys.stdin.buffer.read().decode("utf-8")
        errors = validate_profile_text(raw, args.kind, args.repo_root.resolve())
    elif args.stdin_base64 is not None:
        config_label = "<stdin-base64>"
        try:
            raw = base64.b64decode(args.stdin_base64, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            errors = [f"invalid base64 UTF-8 input: {exc}"]
        else:
            errors = validate_profile_text(raw, args.kind, args.repo_root.resolve())
    else:
        config_path = args.config.resolve()
        config_label = str(config_path)
        errors = validate_profile(config_path, args.kind, args.repo_root.resolve())
    report = {
        "config": config_label,
        "kind": args.kind,
        "errors": errors,
        "verdict": "PASS" if not errors else "FAIL",
    }
    sys.stdout.buffer.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

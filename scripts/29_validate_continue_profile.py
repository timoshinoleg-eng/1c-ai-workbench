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
import json
import re
import sys
from pathlib import Path
from typing import Any

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
    return len(compact) >= 24 and re.fullmatch(r"[A-Za-z0-9+/=_\-]{24,}", compact) is not None


def _model_roles(model: dict[str, Any]) -> list[str]:
    roles = model.get("roles")
    if roles is None:
        return []
    if not isinstance(roles, list):
        return [str(roles)]
    return [str(role) for role in roles]


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
                    errors.append(f"{label}.apiKey must be a ${{{{ secrets.* }}}} reference, got {api_key!r}")


def _online_checks(data: dict[str, Any], errors: list[str]) -> None:
    models = data.get("models") or []
    groq_models = [m for m in models if isinstance(m, dict) and m.get("provider") == "groq"]
    if not groq_models:
        errors.append("Online Hybrid requires at least one Groq cloud model")

    groq_model_ids = {str(m.get("model")) for m in groq_models}
    missing = REQUIRED_GROQ_MODELS - groq_model_ids
    if missing:
        errors.append(f"Online Hybrid is missing selectable Groq models: {sorted(missing)}")

    for model in groq_models:
        label = f"groq model {model.get('model')!r}"
        roles = set(_model_roles(model))
        if not {"chat", "edit", "apply"}.issubset(roles):
            errors.append(f"{label} must have chat/edit/apply roles, got {sorted(roles)}")
        if model.get("apiKey") != GROQ_KEY_LITERAL:
            errors.append(f"{label} apiKey must be exactly {GROQ_KEY_LITERAL!r}")
        capabilities = model.get("capabilities") or []
        if "tool_use" not in [str(c) for c in capabilities]:
            errors.append(f"{label} should declare the 'tool_use' capability for Agent-mode MCP access")

    ollama = [m for m in models if isinstance(m, dict) and m.get("provider") == "ollama"]
    autocomplete = [m for m in ollama if str(m.get("model")) == OLLAMA_AUTOCOMPLETE_MODEL]
    if not autocomplete:
        errors.append(f"Online Hybrid requires Ollama autocomplete model {OLLAMA_AUTOCOMPLETE_MODEL!r}")
    for model in autocomplete:
        if set(_model_roles(model)) != {"autocomplete"}:
            errors.append(f"Ollama model {OLLAMA_AUTOCOMPLETE_MODEL!r} must have only the autocomplete role")

    servers = data.get("mcpServers") or []
    server_names = {str(s.get("name")) for s in servers if isinstance(s, dict)}
    for required in ("1c-code-index", "1c-help-index"):
        if required not in server_names:
            errors.append(f"Online Hybrid requires MCP server {required!r}")

    by_name = {str(s.get("name")): s for s in servers if isinstance(s, dict)}
    code = by_name.get("1c-code-index")
    if code is not None:
        args = [str(a) for a in (code.get("args") or [])]
        command = str(code.get("command") or "")
        if not command.endswith("bsl-indexer.exe"):
            errors.append("1c-code-index command must point at bsl-indexer.exe")
        if "serve" not in args or "--transport" not in args or "stdio" not in args:
            errors.append("1c-code-index args must preserve 'serve --transport stdio'")
        if not any(a.startswith("onec=") for a in args):
            errors.append("1c-code-index args must include an 'onec=' source-mirror path")
        if "CODE_INDEX_HOME" not in (code.get("env") or {}):
            errors.append("1c-code-index env must set CODE_INDEX_HOME")

    help_server = by_name.get("1c-help-index")
    if help_server is not None:
        env = help_server.get("env") or {}
        if env.get("HELP_INDEX_MODE") != "readonly":
            errors.append("1c-help-index env must set HELP_INDEX_MODE=readonly")


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
    if "apibase" in lowered:
        errors.append("Offline Lite must not contain a cloud apiBase")
    for url_marker in ("api.groq.com", "api.openai.com", "https://api."):
        if url_marker in lowered:
            errors.append(f"Offline Lite must not contain a cloud API URL ({url_marker})")

    models = data.get("models") or []
    all_roles: set[str] = set()
    for model in models:
        if not isinstance(model, dict):
            continue
        provider = str(model.get("provider")).lower()
        if provider in CLOUD_PROVIDERS or provider != "ollama":
            errors.append(f"Offline Lite allows only the ollama provider, got {provider!r}")
        all_roles.update(_model_roles(model))
    if all_roles and all_roles != {"autocomplete"}:
        errors.append(f"Offline Lite roles must be exactly autocomplete, got {sorted(all_roles)}")

    name = str(data.get("name") or "")
    if "autocomplete only" not in name.lower():
        errors.append("Offline Lite name must state 'autocomplete only'")


def validate_profile(config_path: Path, kind: str, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not config_path.is_file():
        return [f"config file not found: {config_path}"]

    raw = config_path.read_text(encoding="utf-8")
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
        _online_checks(data, errors)
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


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate generated Continue Thin Client profiles.")
    parser.add_argument("--config", type=Path, required=True, help="Generated config.yaml to validate")
    parser.add_argument("--kind", choices=("online", "offline"), required=True, help="Expected profile kind")
    parser.add_argument("--repo-root", type=Path, default=root, help="Workbench root for rules/ignore checks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_profile(args.config.resolve(), args.kind, args.repo_root.resolve())
    report = {
        "config": str(args.config),
        "kind": args.kind,
        "errors": errors,
        "verdict": "PASS" if not errors else "FAIL",
    }
    sys.stdout.buffer.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

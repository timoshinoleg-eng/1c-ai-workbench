from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "tools" / "ibcmd-bridge" / "server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("ibcmd_bridge_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load ibcmd bridge server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exe_path_rejects_client_selected_absolute_executable(monkeypatch, tmp_path):
    server = load_server_module()
    candidate = tmp_path / "unexpected.exe"
    candidate.write_text("not executable", encoding="utf-8")
    monkeypatch.delenv("IBCMD_EXE", raising=False)

    with pytest.raises(PermissionError, match="configured server-side only"):
        server.exe_path(str(candidate))


def test_exe_path_accepts_exact_server_configured_executable(monkeypatch, tmp_path):
    server = load_server_module()
    candidate = tmp_path / "ibcmd.exe"
    candidate.write_text("configured binary", encoding="utf-8")
    monkeypatch.setenv("IBCMD_EXE", str(candidate))

    assert server.exe_path(str(candidate)) == str(candidate.resolve())
    assert server.exe_path(None) == str(candidate.resolve())


def test_display_workbench_path_redacts_external_path(tmp_path):
    server = load_server_module()
    internal = tmp_path / "workspace" / "generated" / "dump"
    internal.mkdir(parents=True)
    external = tmp_path / "outside"
    external.mkdir()

    assert server.display_workbench_path(internal, internal.parents[1]) == "generated/dump"
    assert server.display_workbench_path(external, internal.parents[1]) == "<external path redacted>"


def test_import_remains_blocked_without_both_write_gate_conditions(monkeypatch):
    server = load_server_module()
    monkeypatch.delenv("IBCMD_ALLOW_WRITE", raising=False)
    result = asyncio.run(
        server._import_config(
            0.0,
            input_dir="generated/input",
            config_file="configs/server.yml",
            confirm_replace=True,
            dry_run=False,
        )
    )
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["blocked"] is True
    assert payload["dry_run"] is True


def test_public_wrappers_do_not_forward_locals():
    source = SERVER_PATH.read_text(encoding="utf-8")
    assert "**locals()" not in source

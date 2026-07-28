# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Behavioral tests for the real MCP stdio readiness handshake."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "30_probe_mcp_stdio.py"


@pytest.fixture()
def fake_mcp_server(tmp_path: Path) -> Path:
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(
        """
import json
import sys

TOOLS = [
    {"name": "search_help", "description": "read", "inputSchema": {"type": "object"}},
    {"name": "help_stats", "description": "read", "inputSchema": {"type": "object"}},
]

for line in sys.stdin:
    message = json.loads(line)
    if message.get("method") == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            },
        }
        print(json.dumps(response), flush=True)
    elif message.get("method") == "tools/list":
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": {"tools": TOOLS}}), flush=True)
""".lstrip(),
        encoding="utf-8",
    )
    return server


def _run_probe(server: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--command",
            sys.executable,
            f"--arg={server}",
            "--timeout",
            "3",
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_probe_performs_initialize_and_tools_list(fake_mcp_server: Path) -> None:
    result = _run_probe(
        fake_mcp_server,
        "--expect-tool=search_help",
        "--expect-tool=help_stats",
        "--forbid-tool=reindex_help",
        "--min-tools",
        "2",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {"verdict": "PASS", "tools": ["help_stats", "search_help"]}


def test_probe_fails_when_required_tool_is_missing(fake_mcp_server: Path) -> None:
    result = _run_probe(fake_mcp_server, "--expect-tool=get_help_topic")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["verdict"] == "FAIL"
    assert "missing required tools" in report["error"]


def test_probe_fails_when_forbidden_tool_is_exposed(fake_mcp_server: Path) -> None:
    result = _run_probe(fake_mcp_server, "--forbid-tool=search_help")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["verdict"] == "FAIL"
    assert "exposed forbidden tools" in report["error"]

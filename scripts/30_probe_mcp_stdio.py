# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Fail-closed MCP stdio readiness probe used by Continue profile checks.

The probe performs the real MCP initialize/initialized/tools-list handshake,
checks the resulting tool set, and terminates the child process. It uses only
the Python standard library and never prints environment-variable values.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, TextIO


class ProbeError(RuntimeError):
    """The MCP process did not satisfy the readiness contract."""


def _reader(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _write_message(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise ProbeError("MCP stdin is unavailable")
    process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _read_response(
    process: subprocess.Popen[str],
    output: queue.Queue[str | None],
    request_id: int,
    timeout: float,
) -> dict[str, Any]:
    while True:
        try:
            line = output.get(timeout=timeout)
        except queue.Empty as exc:
            raise ProbeError(f"timed out waiting for MCP response id={request_id}") from exc
        if line is None:
            code = process.poll()
            raise ProbeError(f"MCP stdout closed before response id={request_id}; exit={code}")
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProbeError("MCP stdout contained a non-JSON protocol line") from exc
        if message.get("id") != request_id:
            continue
        if "error" in message:
            error = message["error"]
            code = error.get("code") if isinstance(error, dict) else "unknown"
            raise ProbeError(f"MCP request id={request_id} failed with code {code}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise ProbeError(f"MCP response id={request_id} has no result object")
        return result


def probe_mcp(
    command: Path,
    arguments: list[str],
    environment: dict[str, str],
    expected_tools: set[str],
    forbidden_tools: set[str],
    minimum_tools: int,
    timeout: float,
) -> list[str]:
    child_env = dict(os.environ)
    child_env.update(environment)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [str(command), *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        creationflags=creationflags,
    )
    if process.stdout is None:
        process.kill()
        raise ProbeError("MCP stdout is unavailable")

    output: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(target=_reader, args=(process.stdout, output), daemon=True)
    reader.start()
    try:
        _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "1c-ai-workbench-readiness", "version": "1.0.0"},
                },
            },
        )
        _read_response(process, output, 1, timeout)
        _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        result = _read_response(process, output, 2, timeout)
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise ProbeError("MCP tools/list result has no tools array")
        names = sorted(str(tool["name"]) for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str))
        if len(names) < minimum_tools:
            raise ProbeError(f"MCP exposed {len(names)} tools; expected at least {minimum_tools}")
        missing = sorted(expected_tools - set(names))
        if missing:
            raise ProbeError(f"MCP is missing required tools: {', '.join(missing)}")
        exposed_forbidden = sorted(forbidden_tools & set(names))
        if exposed_forbidden:
            raise ProbeError(f"MCP exposed forbidden tools: {', '.join(exposed_forbidden)}")
        return names
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def _parse_environment(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        name, separator, content = value.partition("=")
        if not separator or not name:
            raise ProbeError("--env values must use NAME=VALUE")
        parsed[name] = content
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe an MCP stdio server and validate tools/list")
    parser.add_argument("--command", type=Path, required=True)
    parser.add_argument("--arg", action="append", default=[], dest="arguments")
    parser.add_argument("--env", action="append", default=[], dest="environment")
    parser.add_argument("--expect-tool", action="append", default=[])
    parser.add_argument("--forbid-tool", action="append", default=[])
    parser.add_argument("--min-tools", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {"verdict": "FAIL", "tools": []}
    try:
        if not args.command.is_file():
            raise ProbeError(f"MCP command not found: {args.command}")
        names = probe_mcp(
            args.command.resolve(),
            args.arguments,
            _parse_environment(args.environment),
            set(args.expect_tool),
            set(args.forbid_tool),
            args.min_tools,
            args.timeout,
        )
        report.update({"verdict": "PASS", "tools": names})
        code = 0
    except (OSError, ProbeError) as exc:
        report["error"] = str(exc)
        code = 1
    sys.stdout.buffer.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

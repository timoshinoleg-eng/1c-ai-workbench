from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, model_validator

mcp = FastMCP(
    name="1c-ibcmd",
    instructions=(
        "MCP bridge for 1C ibcmd. Export is callable; import is blocked unless "
        "IBCMD_ALLOW_WRITE=1 and confirm_replace=true."
    ),
)

WORKBENCH_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_LIMIT = 12000
SECRET_TEXT_RE = re.compile(
    r"(?i)(--(?:password|db-pwd)=)[^\s;]+|((?:password|pwd|token|secret)=)[^\s;]+|((?:Password|Pwd)=)[^;\r\n]+"
)


class ArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConnectionArgs(ArgsModel):
    ibcmd_exe: str | None = Field(default=None, description="Path to ibcmd.exe or command name.")
    config_file: str | None = Field(default=None, description="Standalone server config.yml path.")
    data_path: str | None = Field(default=None, description="Standalone server data directory.")
    db_path: str | None = Field(default=None, description="File infobase path.")
    dbms: str | None = Field(
        default=None,
        description="DBMS name for server infobase, for example mssqlserver.",
    )
    db_server: str | None = None
    db_name: str | None = None
    db_user: str | None = None
    db_password_env: str | None = Field(default=None, description="Environment variable holding DB password.")
    user: str | None = Field(default=None, description="1C infobase user.")
    password_env: str | None = Field(default=None, description="Environment variable holding 1C user password.")

    @model_validator(mode="after")
    def validate_connection(self) -> ConnectionArgs:
        has_file = bool(self.db_path)
        has_server = bool(self.db_server and self.db_name)
        has_config = bool(self.config_file)
        if sum([has_file, has_server, has_config]) != 1:
            raise ValueError("provide exactly one connection mode: db_path, db_server+db_name, or config_file")
        return self


class ProbeArgs(ArgsModel):
    ibcmd_exe: str | None = None
    timeout_sec: int = Field(default=10, ge=1, le=60)


class ExportArgs(ConnectionArgs):
    output_dir: str = Field(min_length=1)
    sync: bool = True
    force: bool = False
    dry_run: bool = True
    timeout_sec: int = Field(default=600, ge=1, le=7200)


class ImportArgs(ConnectionArgs):
    input_dir: str = Field(min_length=1)
    confirm_replace: bool = False
    dry_run: bool = True
    timeout_sec: int = Field(default=600, ge=1, le=7200)


class EdtPlanArgs(ExportArgs):
    edt_project_dir: str = Field(min_length=1)
    workspace_dir: str = Field(min_length=1)
    edt_cli_exe: str = "1cedtcli"
    platform_version: str | None = None


class ExportAndIndexArgs(ExportArgs):
    workbench_root: str = Field(default_factory=lambda: str(WORKBENCH_ROOT))
    index_alias: str = Field(default="onec", min_length=1)
    index_after_export: bool = True


class CompareExportsArgs(ArgsModel):
    left_dir: str = Field(min_length=1)
    right_dir: str = Field(min_length=1)
    limit: int = Field(default=200, ge=1, le=2000)


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def json_result(tool: str, ok: bool, started: float, data: dict[str, Any]) -> str:
    payload = {"tool": tool, "ok": ok, "elapsed_ms": elapsed_ms(started), **data}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def exe_path(value: str | None) -> str:
    raw = value or os.environ.get("IBCMD_EXE") or "ibcmd"
    if raw == "ibcmd":
        return raw
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ValueError(
            "ibcmd_exe / IBCMD_EXE must be either the literal 'ibcmd' (resolved via PATH) "
            f"or an absolute path to an existing executable. Got relative value: {raw}"
        )
    if not candidate.exists():
        raise FileNotFoundError(f"ibcmd executable not found at resolved path: {candidate}")
    return str(candidate)


def env_secret(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"environment variable is not set: {name}")
    return value


def redacted(command: list[str]) -> list[str]:
    secret_flags = {"--password", "--db-pwd", "-P"}
    redacted_command: list[str] = []
    skip_next = False
    for item in command:
        if skip_next:
            redacted_command.append("***")
            skip_next = False
            continue
        if item in secret_flags:
            redacted_command.append(item)
            skip_next = True
            continue
        if item.startswith("--password=") or item.startswith("--db-pwd="):
            redacted_command.append(item.split("=", 1)[0] + "=***")
        else:
            redacted_command.append(item)
    return redacted_command


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    return SECRET_TEXT_RE.sub(lambda match: f"{next(group for group in match.groups() if group)}***", text)


def truncate_output(text: str | bytes | None) -> tuple[str, bool]:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    redacted_text = redact_text(text)
    if len(redacted_text) <= OUTPUT_LIMIT:
        return redacted_text, False
    return redacted_text[-OUTPUT_LIMIT:], True


def path_within_root(path: Path, root: Path = WORKBENCH_ROOT) -> Path | None:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def resolve_workbench_path(
    value: str,
    field_name: str,
    *,
    root: Path = WORKBENCH_ROOT,
    must_exist: bool = False,
    allow_file: bool = False,
) -> Path:
    candidate = Path(value).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    safe_path = path_within_root(resolved, root)
    if safe_path is None:
        raise PermissionError(f"{field_name} must be inside workbench root: {value}")
    if must_exist and not safe_path.exists():
        raise FileNotFoundError(f"{field_name} not found: {safe_path}")
    if safe_path.exists() and safe_path.is_file() and not allow_file:
        raise NotADirectoryError(f"{field_name} must be a directory: {safe_path}")
    return safe_path


def add_connection(command: list[str], args: ConnectionArgs) -> None:
    if args.config_file:
        command.extend(["-c", args.config_file])
    if args.data_path:
        command.append(f"--data={args.data_path}")
    if args.db_path:
        command.append(f"--db-path={args.db_path}")
    if args.db_server and args.db_name:
        if args.dbms:
            command.append(f"--dbms={args.dbms}")
        command.append(f"--db-server={args.db_server}")
        command.append(f"--db-name={args.db_name}")
        if args.db_user:
            command.append(f"--db-user={args.db_user}")
        db_password = env_secret(args.db_password_env)
        if db_password:
            command.append(f"--db-pwd={db_password}")
    if args.user:
        command.extend(["-u", args.user])
    password = env_secret(args.password_env)
    if password:
        command.extend(["-P", password])


def run_command(command: list[str], timeout_sec: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = truncate_output(exc.stdout)
        stderr, stderr_truncated = truncate_output(exc.stderr)
        return {
            "exit_code": None,
            "timeout": True,
            "command": redacted(command),
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    stdout, stdout_truncated = truncate_output(completed.stdout)
    stderr, stderr_truncated = truncate_output(completed.stderr)
    return {
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_dir(root: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in root.rglob("*"):
        safe_path = path_within_root(path, root)
        if safe_path and safe_path.is_file() and ".code-index" not in safe_path.parts:
            rows[safe_path.relative_to(root).as_posix()] = file_hash(safe_path)
    return rows


def export_command(args: ExportArgs) -> list[str]:
    command = [exe_path(args.ibcmd_exe), "infobase", "config", "export"]
    add_connection(command, args)
    if args.sync:
        command.append("--sync")
    if args.force:
        command.append("--force")
    command.append(args.output_dir)
    return command


def import_command(args: ImportArgs) -> list[str]:
    command = [exe_path(args.ibcmd_exe), "infobase", "config", "import"]
    add_connection(command, args)
    command.append(args.input_dir)
    return command


async def safe(tool: str, runner, **kwargs: object) -> str:
    started = time.perf_counter()
    try:
        return await runner(started, **kwargs)
    except Exception as exc:
        return json_result(tool, False, started, {"error": str(exc)})


async def _probe(started: float, **kwargs: object) -> str:
    args = ProbeArgs.model_validate(kwargs)
    command = [exe_path(args.ibcmd_exe), "--version"]
    try:
        result = run_command(command, args.timeout_sec)
    except FileNotFoundError:
        return json_result(
            "ibcmd_probe",
            False,
            started,
            {"error": "ibcmd not found", "command": redacted(command)},
        )
    if result["exit_code"] != 0:
        help_command = [exe_path(args.ibcmd_exe), "--help"]
        help_result = run_command(help_command, args.timeout_sec)
        return json_result(
            "ibcmd_probe",
            help_result["exit_code"] == 0,
            started,
            {"command": redacted(help_command), "result": help_result},
        )
    return json_result("ibcmd_probe", True, started, {"command": redacted(command), "result": result})


async def _export_config(started: float, **kwargs: object) -> str:
    args = ExportArgs.model_validate(kwargs)
    output_dir = resolve_workbench_path(args.output_dir, "output_dir")
    command = export_command(args)
    command[-1] = str(output_dir)
    if args.dry_run:
        return json_result(
            "ibcmd_export_config",
            True,
            started,
            {
                "dry_run": True,
                "command": redacted(command),
                "output_dir": str(output_dir),
            },
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = run_command(command, args.timeout_sec)
    except FileNotFoundError:
        return json_result(
            "ibcmd_export_config",
            False,
            started,
            {"error": "ibcmd not found", "command": redacted(command)},
        )
    return json_result(
        "ibcmd_export_config",
        result["exit_code"] == 0,
        started,
        {
            "dry_run": False,
            "command": redacted(command),
            "result": result,
            "output_dir": str(output_dir),
        },
    )


async def _import_config(started: float, **kwargs: object) -> str:
    args = ImportArgs.model_validate(kwargs)
    command = import_command(args)
    write_enabled = os.environ.get("IBCMD_ALLOW_WRITE") == "1"
    if not write_enabled or not args.confirm_replace:
        return json_result(
            "ibcmd_import_config",
            False,
            started,
            {
                "blocked": True,
                "reason": "config import replaces the target infobase configuration; set IBCMD_ALLOW_WRITE=1 and confirm_replace=true",
                "dry_run": True,
                "command": redacted(command),
            },
        )
    input_dir = resolve_workbench_path(args.input_dir, "input_dir", must_exist=True)
    command[-1] = str(input_dir)
    if args.dry_run:
        return json_result(
            "ibcmd_import_config",
            True,
            started,
            {
                "dry_run": True,
                "command": redacted(command),
                "input_dir": str(input_dir),
            },
        )
    try:
        result = run_command(command, args.timeout_sec)
    except FileNotFoundError:
        return json_result(
            "ibcmd_import_config",
            False,
            started,
            {"error": "ibcmd not found", "command": redacted(command)},
        )
    return json_result(
        "ibcmd_import_config",
        result["exit_code"] == 0,
        started,
        {
            "dry_run": False,
            "command": redacted(command),
            "result": result,
            "input_dir": str(input_dir),
        },
    )


async def _edt_plan(started: float, **kwargs: object) -> str:
    args = EdtPlanArgs.model_validate(kwargs)
    output_dir = resolve_workbench_path(args.output_dir, "output_dir")
    workspace_dir = resolve_workbench_path(args.workspace_dir, "workspace_dir")
    edt_project_dir = resolve_workbench_path(args.edt_project_dir, "edt_project_dir", must_exist=True)
    export = redacted(export_command(args))
    edt = [
        args.edt_cli_exe,
        "-data",
        str(workspace_dir),
        "-command",
        "import",
        "--project",
        str(edt_project_dir),
        "--configuration-files",
        str(output_dir),
    ]
    if args.platform_version:
        edt.extend(["--version", args.platform_version])
    cleanup = [
        args.edt_cli_exe,
        "-data",
        str(workspace_dir),
        "-command",
        "clean-up-source",
        "--project",
        str(edt_project_dir),
    ]
    return json_result(
        "ibcmd_build_edt_import_plan",
        True,
        started,
        {
            "dry_run": True,
            "steps": [
                {"name": "export_xml_with_ibcmd", "command": export},
                {"name": "import_xml_to_edt_project", "command": edt},
                {"name": "cleanup_edt_source", "command": cleanup},
            ],
        },
    )


async def _export_and_index(started: float, **kwargs: object) -> str:
    args = ExportAndIndexArgs.model_validate(kwargs)
    workbench_root = resolve_workbench_path(args.workbench_root, "workbench_root", must_exist=True)
    output_dir = resolve_workbench_path(args.output_dir, "output_dir", root=workbench_root)
    export = export_command(args)
    export[-1] = str(output_dir)
    bsl_indexer = workbench_root / "tools" / "code-index-mcp" / "target" / "release" / "bsl-indexer.exe"
    init_command = [str(bsl_indexer), "init", "--path", str(output_dir)]
    index_command = [
        str(bsl_indexer),
        "index",
        "--path",
        f"{args.index_alias}={output_dir}",
    ]

    if args.dry_run:
        return json_result(
            "ibcmd_export_and_index",
            True,
            started,
            {
                "dry_run": True,
                "steps": [
                    {"name": "ibcmd_export_config", "command": redacted(export)},
                    {"name": "bsl_indexer_init", "command": init_command},
                    {"name": "bsl_indexer_index", "command": index_command},
                ],
            },
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        export_result = run_command(export, args.timeout_sec)
    except FileNotFoundError:
        return json_result(
            "ibcmd_export_and_index",
            False,
            started,
            {"error": "ibcmd not found", "command": redacted(export)},
        )
    if export_result["exit_code"] != 0:
        return json_result(
            "ibcmd_export_and_index",
            False,
            started,
            {
                "step": "ibcmd_export_config",
                "command": redacted(export),
                "result": export_result,
            },
        )
    if not args.index_after_export:
        return json_result(
            "ibcmd_export_and_index",
            True,
            started,
            {
                "step": "ibcmd_export_config",
                "command": redacted(export),
                "result": export_result,
                "indexed": False,
            },
        )
    if not bsl_indexer.exists():
        return json_result(
            "ibcmd_export_and_index",
            False,
            started,
            {
                "error": "bsl-indexer.exe not found",
                "path": str(bsl_indexer),
                "export_result": export_result,
            },
        )
    init_result = run_command(init_command, 120)
    if init_result["exit_code"] != 0:
        return json_result(
            "ibcmd_export_and_index",
            False,
            started,
            {
                "step": "bsl_indexer_init",
                "command": init_command,
                "result": init_result,
            },
        )
    index_result = run_command(index_command, args.timeout_sec)
    return json_result(
        "ibcmd_export_and_index",
        index_result["exit_code"] == 0,
        started,
        {
            "steps": [
                {
                    "name": "ibcmd_export_config",
                    "command": redacted(export),
                    "result": export_result,
                },
                {
                    "name": "bsl_indexer_init",
                    "command": init_command,
                    "result": init_result,
                },
                {
                    "name": "bsl_indexer_index",
                    "command": index_command,
                    "result": index_result,
                },
            ],
        },
    )


async def _compare_exports(started: float, **kwargs: object) -> str:
    args = CompareExportsArgs.model_validate(kwargs)
    left = resolve_workbench_path(args.left_dir, "left_dir", must_exist=True)
    right = resolve_workbench_path(args.right_dir, "right_dir", must_exist=True)
    if not left.is_dir() or not right.is_dir():
        return json_result(
            "ibcmd_compare_exports",
            False,
            started,
            {
                "error": "left_dir and right_dir must be existing directories",
                "left_dir": str(left),
                "right_dir": str(right),
            },
        )
    left_map = snapshot_dir(left)
    right_map = snapshot_dir(right)
    left_keys = set(left_map)
    right_keys = set(right_map)
    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    changed = sorted(path for path in left_keys & right_keys if left_map[path] != right_map[path])
    return json_result(
        "ibcmd_compare_exports",
        True,
        started,
        {
            "left_dir": str(left),
            "right_dir": str(right),
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
            },
            "added": added[: args.limit],
            "removed": removed[: args.limit],
            "changed": changed[: args.limit],
        },
    )


@mcp.tool()
async def ibcmd_probe(ibcmd_exe: str | None = None, timeout_sec: int = 10) -> str:
    """RU: Проверить доступность ibcmd. EN: Probe ibcmd version/help."""
    return await safe("ibcmd_probe", _probe, ibcmd_exe=ibcmd_exe, timeout_sec=timeout_sec)


@mcp.tool()
async def ibcmd_export_config(
    output_dir: str,
    ibcmd_exe: str | None = None,
    config_file: str | None = None,
    data_path: str | None = None,
    db_path: str | None = None,
    dbms: str | None = None,
    db_server: str | None = None,
    db_name: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    user: str | None = None,
    password_env: str | None = None,
    sync: bool = True,
    force: bool = False,
    dry_run: bool = True,
    timeout_sec: int = 600,
) -> str:
    """RU: Экспортировать конфигурацию ИБ в XML-файлы. EN: Export infobase configuration to XML files."""
    return await safe("ibcmd_export_config", _export_config, **locals())


@mcp.tool()
async def ibcmd_import_config(
    input_dir: str,
    ibcmd_exe: str | None = None,
    config_file: str | None = None,
    data_path: str | None = None,
    db_path: str | None = None,
    dbms: str | None = None,
    db_server: str | None = None,
    db_name: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    user: str | None = None,
    password_env: str | None = None,
    confirm_replace: bool = False,
    dry_run: bool = True,
    timeout_sec: int = 600,
) -> str:
    """RU: Импортировать XML в ИБ с явным write-gate. EN: Import XML into an infobase with explicit write gate."""
    return await safe("ibcmd_import_config", _import_config, **locals())


@mcp.tool()
async def ibcmd_build_edt_import_plan(
    output_dir: str,
    edt_project_dir: str,
    workspace_dir: str,
    ibcmd_exe: str | None = None,
    config_file: str | None = None,
    data_path: str | None = None,
    db_path: str | None = None,
    dbms: str | None = None,
    db_server: str | None = None,
    db_name: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    user: str | None = None,
    password_env: str | None = None,
    sync: bool = True,
    force: bool = False,
    dry_run: bool = True,
    timeout_sec: int = 600,
    edt_cli_exe: str = "1cedtcli",
    platform_version: str | None = None,
) -> str:
    """RU: Построить план экспорта ibcmd и импорта в EDT. EN: Build XML export plus EDT import command plan."""
    return await safe("ibcmd_build_edt_import_plan", _edt_plan, **locals())


@mcp.tool()
async def ibcmd_export_and_index(
    output_dir: str,
    ibcmd_exe: str | None = None,
    config_file: str | None = None,
    data_path: str | None = None,
    db_path: str | None = None,
    dbms: str | None = None,
    db_server: str | None = None,
    db_name: str | None = None,
    db_user: str | None = None,
    db_password_env: str | None = None,
    user: str | None = None,
    password_env: str | None = None,
    sync: bool = True,
    force: bool = False,
    dry_run: bool = True,
    timeout_sec: int = 600,
    workbench_root: str = str(WORKBENCH_ROOT),
    index_alias: str = "onec",
    index_after_export: bool = True,
) -> str:
    """RU: Экспортировать конфигурацию ibcmd и переиндексировать dump. EN: Export configuration and refresh the code index."""
    return await safe("ibcmd_export_and_index", _export_and_index, **locals())


@mcp.tool()
async def ibcmd_compare_exports(left_dir: str, right_dir: str, limit: int = 200) -> str:
    """RU: Сравнить две XML-выгрузки конфигурации. EN: Compare two XML configuration export directories."""
    return await safe(
        "ibcmd_compare_exports",
        _compare_exports,
        left_dir=left_dir,
        right_dir=right_dir,
        limit=limit,
    )


if __name__ == "__main__":
    mcp.run()

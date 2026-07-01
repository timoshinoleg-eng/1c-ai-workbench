from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import Field

from .common import (
    SourcePathArgs,
    resolve_existing_path,
    resolve_source_root,
    result_json,
    timer,
)

WORKBENCH_ROOT = Path(__file__).resolve().parents[3]


class SubsystemInfoArgs(SourcePathArgs):
    subsystem_path: str = Field(min_length=1, description="Path to subsystem XML or Subsystems/ directory.")
    mode: str = Field(default="overview", pattern="^(overview|content|ci|tree|full)$")
    name: str | None = Field(default=None, description="Filter by name/type.")
    limit: int = Field(default=150, ge=1)


async def run(**kwargs: object) -> str:
    started = timer()
    args = SubsystemInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)

    target = resolve_existing_path(root, args.subsystem_path, ".xml")
    if target is None:
        return result_json(
            "subsystem_info",
            False,
            {"error": f"target not found: {args.subsystem_path}"},
            started.elapsed_ms(),
        )

    script_path = (
        WORKBENCH_ROOT / "tools" / "cc-1c-skills" / ".claude" / "skills" / "subsystem-info" / "scripts" / "subsystem-info.py"
    )
    if not script_path.exists():
        return result_json(
            "subsystem_info",
            False,
            {"error": f"script not found: {script_path}"},
            started.elapsed_ms(),
        )

    cmd = [
        sys.executable,
        str(script_path),
        "-SubsystemPath",
        str(target),
        "-Mode",
        args.mode,
        "-Limit",
        str(args.limit),
    ]
    if args.name:
        cmd += ["-Name", args.name]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        ok = proc.returncode == 0
        return result_json(
            "subsystem_info",
            ok,
            {
                "source_root": str(root),
                "target_path": str(target),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            },
            started.elapsed_ms(),
        )
    except Exception as exc:
        return result_json("subsystem_info", False, {"error": str(exc)}, started.elapsed_ms())

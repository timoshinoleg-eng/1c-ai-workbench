from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pydantic import Field

from .common import (
    SourcePathArgs,
    resolve_source_root,
    result_json,
    timer,
)

WORKBENCH_ROOT = Path(__file__).resolve().parents[3]


class CfInfoArgs(SourcePathArgs):
    mode: str = Field(default="overview", pattern="^(overview|brief|full)$")
    section: str | None = Field(default=None, description="Drill-down section (e.g. home-page)")
    limit: int = Field(default=150, ge=1)


async def run(**kwargs: object) -> str:
    started = timer()
    args = CfInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)

    cfg = root / "Configuration.xml"
    if not cfg.exists():
        return result_json(
            "cf_info",
            False,
            {"error": f"Configuration.xml not found in {root}"},
            started.elapsed_ms(),
        )

    script_path = WORKBENCH_ROOT / "tools" / "cc-1c-skills" / ".claude" / "skills" / "cf-info" / "scripts" / "cf-info.py"
    if not script_path.exists():
        return result_json(
            "cf_info",
            False,
            {"error": f"script not found: {script_path}"},
            started.elapsed_ms(),
        )

    cmd = [
        sys.executable,
        str(script_path),
        "-ConfigPath",
        str(cfg),
        "-Mode",
        args.mode,
        "-Limit",
        str(args.limit),
    ]
    if args.section:
        cmd += ["-Section", args.section]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        ok = proc.returncode == 0
        return result_json(
            "cf_info",
            ok,
            {
                "source_root": str(root),
                "config_path": str(cfg),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            },
            started.elapsed_ms(),
        )
    except Exception as exc:
        return result_json("cf_info", False, {"error": str(exc)}, started.elapsed_ms())

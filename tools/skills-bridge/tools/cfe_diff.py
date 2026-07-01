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


class CfeDiffArgs(SourcePathArgs):
    extension_path: str = Field(min_length=1, description="Path to extension dump root.")
    config_path: str = Field(min_length=1, description="Path to base config dump root.")
    mode: str = Field(default="A", pattern="^(A|B)$")


async def run(**kwargs: object) -> str:
    started = timer()
    args = CfeDiffArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)

    ext_path = resolve_existing_path(root, args.extension_path, "")
    cfg_path = resolve_existing_path(root, args.config_path, "")

    if ext_path is None:
        return result_json(
            "cfe_diff",
            False,
            {"error": f"extension path not found: {args.extension_path}"},
            started.elapsed_ms(),
        )
    if cfg_path is None:
        return result_json(
            "cfe_diff",
            False,
            {"error": f"config path not found: {args.config_path}"},
            started.elapsed_ms(),
        )

    script_path = WORKBENCH_ROOT / "tools" / "cc-1c-skills" / ".claude" / "skills" / "cfe-diff" / "scripts" / "cfe-diff.py"
    if not script_path.exists():
        return result_json(
            "cfe_diff",
            False,
            {"error": f"script not found: {script_path}"},
            started.elapsed_ms(),
        )

    cmd = [
        sys.executable,
        str(script_path),
        "-ExtensionPath",
        str(ext_path),
        "-ConfigPath",
        str(cfg_path),
        "-Mode",
        args.mode,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60)
        ok = proc.returncode == 0
        return result_json(
            "cfe_diff",
            ok,
            {
                "source_root": str(root),
                "extension_path": str(ext_path),
                "config_path": str(cfg_path),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            },
            started.elapsed_ms(),
        )
    except Exception as exc:
        return result_json("cfe_diff", False, {"error": str(exc)}, started.elapsed_ms())

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


class MetaValidateArgs(SourcePathArgs):
    object_path: str = Field(min_length=1, description="Path to metadata object XML.")
    detailed: bool = Field(default=False, description="Detailed output.")
    max_errors: int = Field(default=30, ge=1)


async def run(**kwargs: object) -> str:
    started = timer()
    args = MetaValidateArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)

    target = resolve_existing_path(root, args.object_path, ".xml")
    if target is None:
        return result_json(
            "meta_validate",
            False,
            {"error": f"target not found: {args.object_path}"},
            started.elapsed_ms(),
        )

    script_path = (
        WORKBENCH_ROOT / "tools" / "cc-1c-skills" / ".claude" / "skills" / "meta-validate" / "scripts" / "meta-validate.py"
    )
    if not script_path.exists():
        return result_json(
            "meta_validate",
            False,
            {"error": f"script not found: {script_path}"},
            started.elapsed_ms(),
        )

    cmd = [
        sys.executable,
        str(script_path),
        "-ObjectPath",
        str(target),
        "-MaxErrors",
        str(args.max_errors),
    ]
    if args.detailed:
        cmd += ["-Detailed"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        ok = proc.returncode == 0
        return result_json(
            "meta_validate",
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
        return result_json("meta_validate", False, {"error": str(exc)}, started.elapsed_ms())

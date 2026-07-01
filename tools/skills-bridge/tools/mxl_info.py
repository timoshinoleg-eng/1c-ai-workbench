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


class MxlInfoArgs(SourcePathArgs):
    template_path: str = Field(min_length=1, description="Path to Template.xml or template name.")
    format: str = Field(default="text", pattern="^(text|json)$")
    with_text: bool = Field(default=False, description="Include text content.")
    max_params: int = Field(default=10, ge=1)
    limit: int = Field(default=150, ge=1)


async def run(**kwargs: object) -> str:
    started = timer()
    args = MxlInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)

    target = resolve_existing_path(root, args.template_path, ".xml")
    if target is None:
        return result_json(
            "mxl_info",
            False,
            {"error": f"target not found: {args.template_path}"},
            started.elapsed_ms(),
        )
    if target.is_dir():
        template_xml = target / "Ext" / "Template.xml"
        if not template_xml.exists():
            return result_json(
                "mxl_info",
                False,
                {"error": f"Template.xml not found in {target}"},
                started.elapsed_ms(),
            )
        target = template_xml

    script_path = WORKBENCH_ROOT / "tools" / "cc-1c-skills" / ".claude" / "skills" / "mxl-info" / "scripts" / "mxl-info.py"
    if not script_path.exists():
        return result_json(
            "mxl_info",
            False,
            {"error": f"script not found: {script_path}"},
            started.elapsed_ms(),
        )

    cmd = [
        sys.executable,
        str(script_path),
        "-TemplatePath",
        str(target),
        "-Format",
        args.format,
        "-MaxParams",
        str(args.max_params),
        "-Limit",
        str(args.limit),
    ]
    if args.with_text:
        cmd += ["-WithText"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        ok = proc.returncode == 0
        return result_json(
            "mxl_info",
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
        return result_json("mxl_info", False, {"error": str(exc)}, started.elapsed_ms())

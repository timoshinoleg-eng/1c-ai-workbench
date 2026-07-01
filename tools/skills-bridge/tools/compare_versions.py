from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import Field

from .common import WORKBENCH_ROOT, ToolArgs, path_within_root, result_json, timer


class CompareVersionsArgs(ToolArgs):
    left_path: str = Field(min_length=1, description="First source-mirror root.")
    right_path: str = Field(min_length=1, description="Second source-mirror root.")
    limit: int = Field(default=200, ge=1, le=1000)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    rows = {}
    for path in root.rglob("*"):
        if path.is_file() and ".code-index" not in path.parts:
            rows[path.relative_to(root).as_posix()] = file_hash(path)
    return rows


async def run(**kwargs: object) -> str:
    started = timer()
    args = CompareVersionsArgs.model_validate(kwargs)
    left = Path(args.left_path).resolve()
    right = Path(args.right_path).resolve()
    if path_within_root(left, WORKBENCH_ROOT) is None or path_within_root(right, WORKBENCH_ROOT) is None:
        return result_json(
            "compare_versions",
            False,
            {"error": "both paths must be inside the workbench root"},
            started.elapsed_ms(),
        )
    if not left.is_dir() or not right.is_dir():
        return result_json(
            "compare_versions",
            False,
            {"error": "both paths must be existing directories"},
            started.elapsed_ms(),
        )
    left_map = snapshot(left)
    right_map = snapshot(right)
    left_keys = set(left_map)
    right_keys = set(right_map)
    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    changed = sorted(path for path in left_keys & right_keys if left_map[path] != right_map[path])
    return result_json(
        "compare_versions",
        True,
        {
            "left": str(left),
            "right": str(right),
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
            },
            "added": added[: args.limit],
            "removed": removed[: args.limit],
            "changed": changed[: args.limit],
        },
        started.elapsed_ms(),
    )

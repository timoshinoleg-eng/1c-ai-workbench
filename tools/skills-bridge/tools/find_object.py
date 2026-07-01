from __future__ import annotations

from pydantic import Field

from .common import (
    SourcePathArgs,
    iter_metadata_xml,
    resolve_source_root,
    result_json,
    timer,
    xml_summary,
)


class FindObjectArgs(SourcePathArgs):
    name: str = Field(min_length=1, description="Metadata object name or substring.")
    path_glob: str | None = Field(default=None, description="Optional glob, for example Catalogs/*.xml.")
    limit: int = Field(default=20, ge=1, le=100)


async def run(**kwargs: object) -> str:
    started = timer()
    args = FindObjectArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    needle = args.name.lower()
    matches = []
    for path in iter_metadata_xml(root, args.path_glob):
        if needle not in path.stem.lower():
            continue
        matches.append(xml_summary(path, root))
        if len(matches) >= args.limit:
            break
    return result_json(
        "find_object",
        True,
        {
            "source_root": str(root),
            "query": args.name,
            "count": len(matches),
            "matches": matches,
        },
        started.elapsed_ms(),
    )

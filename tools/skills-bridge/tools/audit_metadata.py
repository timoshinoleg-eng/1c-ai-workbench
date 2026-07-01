from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from .common import (
    SourcePathArgs,
    iter_metadata_xml,
    resolve_source_root,
    result_json,
    timer,
    xml_summary,
)


class AuditMetadataArgs(SourcePathArgs):
    limit: int = Field(default=100, ge=1, le=1000)


async def run(**kwargs: object) -> str:
    started = timer()
    args = AuditMetadataArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    names: dict[str, list[dict[str, str]]] = defaultdict(list)
    empty_synonyms = []
    empty_objects = []
    total = 0

    for path in iter_metadata_xml(root):
        total += 1
        summary = xml_summary(path, root)
        names[summary["name"].lower()].append({"name": summary["name"], "path": summary["path"], "type": summary["type"]})
        if not summary["synonym"]:
            empty_synonyms.append(
                {
                    "name": summary["name"],
                    "path": summary["path"],
                    "type": summary["type"],
                }
            )
        if not summary["children_count"] and summary["type"] not in {
            "Role",
            "Subsystem",
        }:
            empty_objects.append(
                {
                    "name": summary["name"],
                    "path": summary["path"],
                    "type": summary["type"],
                }
            )

    duplicates = [items for items in names.values() if len(items) > 1]
    findings = {
        "duplicates": duplicates[: args.limit],
        "empty_synonyms": empty_synonyms[: args.limit],
        "empty_objects": empty_objects[: args.limit],
    }
    return result_json(
        "audit_metadata",
        True,
        {
            "source_root": str(root),
            "objects_scanned": total,
            "finding_counts": {k: len(v) for k, v in findings.items()},
            "findings": findings,
        },
        started.elapsed_ms(),
    )

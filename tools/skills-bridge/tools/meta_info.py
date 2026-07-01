from __future__ import annotations

from pydantic import Field

from .common import (
    SourcePathArgs,
    markdown_table,
    resolve_source_root,
    resolve_xml_path,
    result_json,
    timer,
    xml_summary,
)


class MetaInfoArgs(SourcePathArgs):
    object_path: str = Field(min_length=1, description="XML path or metadata object name.")
    mode: str = Field(default="overview", pattern="^(overview|brief|full)$")
    name: str | None = Field(default=None, description="Optional child name drill-down.")


async def run(**kwargs: object) -> str:
    started = timer()
    args = MetaInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    path = resolve_xml_path(root, args.object_path)
    if path is None:
        return result_json(
            "meta_info",
            False,
            {"error": f"object not found: {args.object_path}"},
            started.elapsed_ms(),
        )

    summary = xml_summary(path, root)
    children = summary["children"]
    if args.name:
        children = [row for row in children if row["name"].lower() == args.name.lower()]

    if args.mode == "brief":
        markdown = f"## {summary['type']} {summary['name']}\n\nChildren: {summary['children_count']}"
    else:
        rows = [[row["kind"], row["name"], row.get("type", ""), row.get("synonym", "")] for row in children]
        markdown = "\n".join(
            [
                f"## {summary['type']} {summary['name']}",
                "",
                f"- Path: `{summary['path']}`",
                f"- UUID: `{summary['uuid']}`" if summary["uuid"] else "- UUID: n/a",
                f"- Synonym: {summary['synonym'] or 'n/a'}",
                f"- Children: {summary['children_count']}",
                "",
                markdown_table(
                    ["Kind", "Name", "Type", "Synonym"],
                    rows,
                    limit=200 if args.mode == "full" else 60,
                ),
            ]
        )
    return result_json(
        "meta_info",
        True,
        {
            "source_root": str(root),
            "path": summary["path"],
            "markdown": markdown,
            "metadata": summary,
            "items": children,
        },
        started.elapsed_ms(),
    )

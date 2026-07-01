from __future__ import annotations

from pathlib import Path

from pydantic import Field

from .common import (
    SourcePathArgs,
    local_name,
    markdown_table,
    parse_xml,
    relative_path,
    resolve_source_root,
    resolve_xml_path,
    result_json,
    timer,
    xml_summary,
)


class RoleInfoArgs(SourcePathArgs):
    role: str = Field(min_length=1, description="Role name or role XML path.")
    limit: int = Field(default=200, ge=1, le=1000)


def rights_path(root: Path, role_xml: Path) -> Path | None:
    candidate = root / "Roles" / role_xml.stem / "Ext" / "Rights.xml"
    return candidate if candidate.exists() else None


async def run(**kwargs: object) -> str:
    started = timer()
    args = RoleInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    path = resolve_xml_path(root, args.role, preferred_dirs=("Roles",))
    if path is None:
        return result_json(
            "role_info",
            False,
            {"error": f"role not found: {args.role}"},
            started.elapsed_ms(),
        )
    summary = xml_summary(path, root)
    rights = []
    rp = rights_path(root, path)
    if rp:
        xml = parse_xml(rp)
        for node in xml.iter():
            tag = local_name(node.tag)
            if tag.lower() in {"right", "objectright", "restrictiontemplate"} or "Right" in tag:
                rights.append(
                    {
                        "kind": tag,
                        "name": node.attrib.get("name", ""),
                        "value": (node.text or "").strip(),
                    }
                )
    rows = [[row["kind"], row["name"], row["value"][:80]] for row in rights[: args.limit]]
    markdown = "\n".join(
        [
            f"## Role `{summary['name']}`",
            "",
            f"- Path: `{summary['path']}`",
            f"- Rights file: `{relative_path(rp, root) if rp else 'n/a'}`",
            f"- Rights entries: {len(rights)}",
            "",
            (markdown_table(["Kind", "Name", "Value"], rows, limit=args.limit) if rows else "No rights entries parsed."),
        ]
    )
    return result_json(
        "role_info",
        True,
        {
            "source_root": str(root),
            "path": summary["path"],
            "rights_path": relative_path(rp, root) if rp else None,
            "markdown": markdown,
            "role": summary,
            "rights": rights[: args.limit],
        },
        started.elapsed_ms(),
    )

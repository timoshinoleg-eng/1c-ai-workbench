from __future__ import annotations

from pathlib import Path

from pydantic import Field

from .common import (
    SourcePathArgs,
    local_name,
    markdown_table,
    parse_xml,
    path_within_root,
    relative_path,
    resolve_source_root,
    result_json,
    timer,
)


class FormInfoArgs(SourcePathArgs):
    form_path: str = Field(min_length=1, description="Form.xml path or object form directory.")
    limit: int = Field(default=150, ge=1, le=500)


def resolve_form(root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return path_within_root(candidate, root)
    direct = (root / value).resolve()
    if not path_within_root(direct, root):
        return None
    if direct.is_file():
        return direct
    if direct.is_dir() and (direct / "Form.xml").exists():
        return direct / "Form.xml"
    matches = [path for path in root.rglob("Form.xml") if value.lower().replace("\\", "/") in path.as_posix().lower()]
    return matches[0] if matches else None


async def run(**kwargs: object) -> str:
    started = timer()
    args = FormInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    path = resolve_form(root, args.form_path)
    if path is None:
        return result_json(
            "form_info",
            False,
            {"error": f"form not found: {args.form_path}"},
            started.elapsed_ms(),
        )
    xml = parse_xml(path)
    attributes = []
    commands = []
    elements = []
    for node in xml.iter():
        tag = local_name(node.tag)
        name = node.attrib.get("name", "")
        if not name:
            continue
        row = {"kind": tag, "name": name, "id": node.attrib.get("id", "")}
        if tag == "Attribute":
            attributes.append(row)
        elif "Command" in tag:
            commands.append(row)
        elif tag not in {"Form", "ExtendedTooltip", "ContextMenu"}:
            elements.append(row)
    rows = [[item["kind"], item["name"], item["id"]] for item in elements[: args.limit]]
    markdown = "\n".join(
        [
            f"## Form `{relative_path(path, root)}`",
            "",
            f"- Attributes: {len(attributes)}",
            f"- Commands: {len(commands)}",
            f"- Elements: {len(elements)}",
            "",
            markdown_table(["Kind", "Name", "ID"], rows, limit=args.limit),
        ]
    )
    return result_json(
        "form_info",
        True,
        {
            "source_root": str(root),
            "path": relative_path(path, root),
            "markdown": markdown,
            "attributes": attributes[: args.limit],
            "commands": commands[: args.limit],
            "elements": elements[: args.limit],
        },
        started.elapsed_ms(),
    )

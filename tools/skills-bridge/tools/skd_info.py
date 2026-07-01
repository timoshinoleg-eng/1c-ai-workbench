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


class SkdInfoArgs(SourcePathArgs):
    path: str = Field(
        min_length=1,
        description="Report/DataProcessor XML path or directory containing SKD files.",
    )
    limit: int = Field(default=200, ge=1, le=1000)


def resolve_skd_targets(root: Path, value: str) -> list[Path]:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        base = path_within_root(candidate, root)
        if base is None:
            return []
    else:
        base = (root / value).resolve()
        if not path_within_root(base, root):
            return []
    if base.is_file():
        return [base]
    if base.is_dir():
        return [path for path in base.rglob("*.xml")]
    matches = [path for path in root.rglob("*.xml") if value.lower().replace("\\", "/") in path.as_posix().lower()]
    return matches[:20]


async def run(**kwargs: object) -> str:
    started = timer()
    args = SkdInfoArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    targets = resolve_skd_targets(root, args.path)
    if not targets:
        return result_json(
            "skd_info",
            False,
            {"error": f"SKD target not found: {args.path}"},
            started.elapsed_ms(),
        )
    datasets = []
    fields = []
    parameters = []
    variants = []
    parse_errors = []
    for path in targets:
        try:
            xml = parse_xml(path)
        except Exception as exc:
            parse_errors.append({"file": relative_path(path, root), "error": str(exc)})
            continue
        for node in xml.iter():
            tag = local_name(node.tag)
            name = node.attrib.get("name") or node.attrib.get("Name") or ""
            text = (node.text or "").strip()
            row = {
                "file": relative_path(path, root),
                "kind": tag,
                "name": name or text[:80],
            }
            lower = tag.lower()
            if "dataset" in lower or "набор" in lower:
                datasets.append(row)
            elif "field" in lower or "поле" in lower:
                fields.append(row)
            elif "parameter" in lower or "параметр" in lower:
                parameters.append(row)
            elif "variant" in lower or "вариант" in lower:
                variants.append(row)
    rows = [[item["file"], item["kind"], item["name"]] for item in (datasets + fields + parameters + variants)[: args.limit]]
    markdown = "\n".join(
        [
            f"## SKD `{args.path}`",
            "",
            f"- Files scanned: {len(targets)}",
            f"- Datasets: {len(datasets)}",
            f"- Fields: {len(fields)}",
            f"- Parameters: {len(parameters)}",
            f"- Variants: {len(variants)}",
            f"- Parse errors: {len(parse_errors)}",
            "",
            (markdown_table(["File", "Kind", "Name"], rows, limit=args.limit) if rows else "No SKD-shaped nodes found."),
        ]
    )
    return result_json(
        "skd_info",
        True,
        {
            "source_root": str(root),
            "markdown": markdown,
            "datasets": datasets[: args.limit],
            "fields": fields[: args.limit],
            "parameters": parameters[: args.limit],
            "variants": variants[: args.limit],
            "parse_errors": parse_errors,
        },
        started.elapsed_ms(),
    )

from __future__ import annotations

import re

from pydantic import Field

from .common import (
    SourcePathArgs,
    extract_bsl_symbols,
    markdown_table,
    relative_path,
    resolve_bsl_path,
    resolve_source_root,
    result_json,
    safe_read_text,
    timer,
)


class ExplainModuleArgs(SourcePathArgs):
    path: str = Field(min_length=1, description="Relative or absolute BSL module path.")
    include_calls: bool = True


CALL_RE = re.compile(r"\b([A-Za-zА-Яа-я_][\wА-Яа-я]*)\s*\(", re.MULTILINE)
NOISE = {
    "Если",
    "Пока",
    "Для",
    "Возврат",
    "Новый",
    "Предупреждение",
    "Сообщить",
    "if",
    "for",
    "while",
    "return",
}


async def run(**kwargs: object) -> str:
    started = timer()
    args = ExplainModuleArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    path = resolve_bsl_path(root, args.path)
    if path is None:
        return result_json(
            "explain_module",
            False,
            {"error": f"module not found: {args.path}"},
            started.elapsed_ms(),
        )

    text = safe_read_text(path)
    symbols = extract_bsl_symbols(text)
    exports = [symbol for symbol in symbols if symbol["export"]]
    calls = []
    if args.include_calls:
        known = {symbol["name"] for symbol in symbols}
        for match in CALL_RE.finditer(text):
            name = match.group(1)
            if name not in NOISE and name not in known:
                calls.append(name)
        calls = sorted(set(calls))[:100]

    rows = [
        [
            s["line"],
            s["kind"],
            s["name"],
            "yes" if s["export"] else "no",
            ", ".join(s["params"]),
        ]
        for s in symbols
    ]
    markdown = "\n".join(
        [
            f"## Module `{relative_path(path, root)}`",
            "",
            f"- Lines: {text.count(chr(10)) + 1}",
            f"- Procedures/functions: {len(symbols)}",
            f"- Exported: {len(exports)}",
            "",
            markdown_table(["Line", "Kind", "Name", "Export", "Params"], rows, limit=100),
        ]
    )
    return result_json(
        "explain_module",
        True,
        {
            "source_root": str(root),
            "path": relative_path(path, root),
            "markdown": markdown,
            "symbols": symbols,
            "external_calls": calls,
        },
        started.elapsed_ms(),
    )

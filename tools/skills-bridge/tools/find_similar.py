from __future__ import annotations

from pydantic import Field

from .common import (
    SourcePathArgs,
    extract_bsl_symbols,
    relative_path,
    resolve_bsl_path,
    resolve_source_root,
    result_json,
    safe_read_text,
    similarity,
    timer,
)


class FindSimilarArgs(SourcePathArgs):
    path: str = Field(min_length=1, description="Reference BSL module path.")
    limit: int = Field(default=10, ge=1, le=50)


def module_fingerprint(text: str) -> str:
    symbols = extract_bsl_symbols(text)
    names = " ".join(symbol["name"] for symbol in symbols)
    first_lines = "\n".join(line.strip() for line in text.splitlines()[:80] if line.strip())
    return f"{names}\n{first_lines[:4000]}"


async def run(**kwargs: object) -> str:
    started = timer()
    args = FindSimilarArgs.model_validate(kwargs)
    root = resolve_source_root(args.source_path)
    base_path = resolve_bsl_path(root, args.path)
    if base_path is None:
        return result_json(
            "find_similar",
            False,
            {"error": f"module not found: {args.path}"},
            started.elapsed_ms(),
        )

    base_fp = module_fingerprint(safe_read_text(base_path))
    matches = []
    for path in root.rglob("*.bsl"):
        if path == base_path:
            continue
        text = safe_read_text(path)
        score = similarity(base_fp, module_fingerprint(text))
        if score >= 0.35:
            matches.append(
                {
                    "path": relative_path(path, root),
                    "score": round(score, 4),
                    "symbols": len(extract_bsl_symbols(text)),
                }
            )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return result_json(
        "find_similar",
        True,
        {
            "source_root": str(root),
            "path": relative_path(base_path, root),
            "matches": matches[: args.limit],
        },
        started.elapsed_ms(),
    )

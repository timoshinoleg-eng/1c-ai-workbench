from __future__ import annotations

import re

from pydantic import Field

from .common import ToolArgs, result_json, timer


class QueryOptimizerArgs(ToolArgs):
    query: str = Field(min_length=1, description="1C query text.")


RULES = [
    (
        "SELECT_STAR",
        re.compile(r"ВЫБРАТЬ\s+\*", re.IGNORECASE),
        "Avoid `ВЫБРАТЬ *`; list fields explicitly.",
    ),
    (
        "NOLOCK",
        re.compile(r"\bДЛЯ\s+ИЗМЕНЕНИЯ\b", re.IGNORECASE),
        "Check lock scope; broad write locks hurt concurrency.",
    ),
    (
        "LIKE_PREFIX",
        re.compile(r"\bПОДОБНО\s+['\"]%", re.IGNORECASE),
        "Leading wildcard disables index-friendly lookup.",
    ),
    (
        "TEMP_TABLE",
        re.compile(r"\bПОМЕСТИТЬ\b", re.IGNORECASE),
        "Temporary table detected; verify indexes and lifecycle.",
    ),
    (
        "LEFT_JOIN",
        re.compile(r"\bЛЕВОЕ\s+СОЕДИНЕНИЕ\b", re.IGNORECASE),
        "Left join detected; verify filter placement after join.",
    ),
    (
        "IN_SUBQUERY",
        re.compile(r"\bВ\s*\(\s*ВЫБРАТЬ\b", re.IGNORECASE),
        "IN subquery detected; compare with join or temp table.",
    ),
    (
        "NO_WHERE",
        re.compile(r"\bИЗ\b(?![\s\S]*\bГДЕ\b)", re.IGNORECASE),
        "No WHERE clause detected.",
    ),
]


async def run(**kwargs: object) -> str:
    started = timer()
    args = QueryOptimizerArgs.model_validate(kwargs)
    findings = []
    for code, pattern, message in RULES:
        matches = list(pattern.finditer(args.query))
        if matches:
            findings.append({"code": code, "count": len(matches), "message": message})
    return result_json(
        "query_optimizer",
        True,
        {"finding_count": len(findings), "findings": findings},
        started.elapsed_ms(),
    )

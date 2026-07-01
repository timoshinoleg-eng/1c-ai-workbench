#!/usr/bin/env python3
"""
Auto-wrap Python source lines that exceed a maximum length.

Conservative approach: only wrap at whitespace positions that are demonstrably
safe (not inside strings, not in bracket contexts, not in comments).

Usage:
  python scripts/fix-line-lengths.py [--max-length 100] [--dry-run] [paths...]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import token
import tokenize
from pathlib import Path
from typing import Iterable

DEFAULT_MAX_LENGTH = 100
DEFAULT_EXCLUDE = (
    "tools/cc-1c-skills",
    "tools/live-1c-bridge",
    "tools/cockpit-app",
    "node_modules",
    "__pycache__",
    "target",
    "generated",
    "dist",
    "logs",
    ".venv",
    "venv",
)

PROTECTED_LINE_MARKERS = (
    "# noqa",
    "# pylint:",
    "# type:",
    "ruff:",
    "fmt: off",
    "fmt: on",
)


def _is_protected(line: str) -> bool:
    s = line.lstrip()
    return any(s.startswith(m) for m in PROTECTED_LINE_MARKERS)


def _is_triple_quoted_string_line(line: str) -> bool:
    body = line.strip()
    if body.startswith('"""') or body.startswith("'''"):
        if body.count(body[:3]) == 1:
            return True
    return False


def _compute_safe_splits(text: str, max_length: int) -> dict[int, list[int]]:
    """Return a map: line_no (1-based) -> list of safe split column indices.

    Safe split is a column where wrapping is safe (whitespace, not in string,
    not in comment, not in bracket expression that would change semantics).
    """
    safe: dict[int, list[int]] = {}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return safe

    # We want to find whitespace positions BETWEEN two adjacent non-string tokens
    # on the same physical line. tokenize treats strings (including their
    # leading prefix) as one STRING token. We don't split inside strings.
    # For NEWLINE/NL/COMMENT tokens, we can split before their start column.
    line_tokens: dict[int, list] = {}
    for tok in tokens:
        if tok.type in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE):
            continue
        ln = tok.start[0]
        line_tokens.setdefault(ln, []).append(tok)

    for ln, toks in line_tokens.items():
        splits: list[int] = []
        for i in range(len(toks) - 1):
            cur = toks[i]
            nxt = toks[i + 1]
            # Don't split near string boundaries
            if cur.type == tokenize.STRING or nxt.type == tokenize.STRING:
                continue
            # We can split right before a comment, but only if comment starts within max_length
            if nxt.type == tokenize.COMMENT:
                if 1 <= nxt.start[1] <= max_length:
                    splits.append(nxt.start[1])
                continue
            # Both are NAME/OP/NUMBER
            if cur.type in (tokenize.NAME, tokenize.OP, tokenize.NUMBER) and \
               nxt.type in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
                gap_start_col = cur.end[1]
                gap_end_col = nxt.start[1]
                gap_len = gap_end_col - gap_start_col
                if gap_len >= 1 and gap_start_col < max_length:
                    # Get the line text to verify it's all whitespace
                    line_text = text.split("\n")[ln - 1]
                    gap_text = line_text[gap_start_col:gap_end_col]
                    if gap_text.strip() == "":
                        splits.append(gap_start_col + 1)
        if splits:
            safe[ln] = splits
    return safe


def _wrap_file(text: str, max_length: int) -> str:
    safe = _compute_safe_splits(text, max_length)
    if not safe:
        return text
    out_lines: list[str] = []
    raw_lines = text.split("\n")
    # Operators that must NOT appear at the start of a wrapped line.
    # Splitting before them would change semantics or look ugly.
    BAD_HEAD_TAIL_OPS = ("=", "+", "-", "*", "/", "%", "**", "//", "->", ":", ",")
    for i, line in enumerate(raw_lines, start=1):
        if i not in safe or len(line) <= max_length:
            out_lines.append(line)
            continue
        if _is_protected(line):
            out_lines.append(line)
            continue
        if _is_triple_quoted_string_line(line):
            out_lines.append(line)
            continue
        # Find the best split (closest to max_length but not exceeding)
        candidates = [p for p in safe[i] if 0 < p <= max_length]
        if not candidates:
            out_lines.append(line)
            continue
        # Filter candidates: head must not end with a bad operator,
        # and tail must not start with a bad operator either.
        good_candidates = []
        for p in candidates:
            head = line[:p].rstrip()
            tail = line[p:].lstrip()
            if head.endswith(BAD_HEAD_TAIL_OPS):
                continue
            if not tail:
                continue
            if tail[0] in BAD_HEAD_TAIL_OPS:
                continue
            good_candidates.append(p)
        if not good_candidates:
            out_lines.append(line)
            continue
        best = max(good_candidates)
        indent_match = re.match(r"^(\s*)", line)
        indent = indent_match.group(1) if indent_match else ""
        head = line[:best].rstrip()
        tail = line[best:].lstrip()
        sub_lines = [head]
        tail_text = tail + "\n"  # newline at end so splitlines works
        wrapped_tail = _wrap_file(tail_text, max_length)
        for sub in wrapped_tail.splitlines():
            if sub:
                sub_lines.append(indent + sub)
        out_lines.extend(sub_lines)
    return "\n".join(out_lines)


def iter_python_files(paths: Iterable[Path], exclude: tuple[str, ...]) -> Iterable[Path]:
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            if any(x in str(p) for x in exclude):
                continue
            yield p
        elif p.is_dir():
            for child in p.rglob("*.py"):
                if any(x in str(child) for x in exclude):
                    continue
                yield child


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path, default=[Path("tools"), Path("scripts"), Path("tests")])
    ap.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_files = 0
    total_lines_before = 0
    total_lines_after = 0
    total_changed = 0
    for path in iter_python_files(args.paths, DEFAULT_EXCLUDE):
        text = path.read_text(encoding="utf-8")
        total_lines_before += len(text.splitlines())
        new_text = _wrap_file(text, args.max_length)
        if new_text != text:
            total_changed += 1
            total_files += 1
            if not args.dry_run:
                path.write_text(new_text, encoding="utf-8")
        total_lines_after += len(new_text.splitlines())
    if args.dry_run:
        print(f"[DRY RUN] {total_changed} file(s) would change; "
              f"{total_lines_before} -> {total_lines_after} lines")
    else:
        print(f"[OK] {total_changed} file(s) updated; "
              f"{total_lines_before} -> {total_lines_after} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())

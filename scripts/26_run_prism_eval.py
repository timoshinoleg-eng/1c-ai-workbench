from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Provider-free evidence evaluation for 1C indexing.")
    parser.add_argument(
        "--binary",
        type=Path,
        default=root / "tools/code-index-mcp/target/release/bsl-indexer.exe",
    )
    parser.add_argument("--fixture", type=Path, default=root / "tests/fixtures/code-index-045")
    parser.add_argument("--cases", type=Path, default=root / "evals/prism-1c/cases.json")
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    return parser.parse_args()


def run(binary: Path, *arguments: str) -> str:
    result = subprocess.run(
        [str(binary), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {binary.name} {' '.join(arguments)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def assert_citation(repo: Path, citation: dict[str, Any]) -> dict[str, Any]:
    relative = Path(citation["path"])
    source = repo / relative
    if not source.is_file():
        raise AssertionError(f"Citation source is missing: {relative.as_posix()}")
    lines = source.read_text(encoding="utf-8").splitlines()
    start = int(citation["line_start"])
    end = int(citation["line_end"])
    if start < 1 or end < start or end > len(lines):
        raise AssertionError(f"Invalid citation range {relative.as_posix()}:{start}-{end}")
    excerpt = "\n".join(lines[start - 1 : end])
    token = str(citation["must_contain"])
    if token not in excerpt:
        raise AssertionError(f"Citation does not support evidence token {token!r}: {relative}:{start}-{end}")
    return {"path": relative.as_posix(), "line_start": start, "line_end": end}


def symbol_result(binary: Path, repo: Path, name: str) -> dict[str, Any]:
    payload = json.loads(run(binary, "query", name, "--path", str(repo), "--language", "bsl", "--json"))
    matches = [item for item in payload.get("functions", []) if item.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(f"Expected one exact symbol {name!r}, got {len(matches)}")
    return matches[0]


def evaluate_case(binary: Path, repo: Path, case: dict[str, Any]) -> dict[str, Any]:
    kind = case["kind"]
    if kind in {"symbol", "body"}:
        match = symbol_result(binary, repo, case["query"])
        if match.get("name") != case["expected_symbol"]:
            raise AssertionError(f"Symbol mismatch for {case['id']}")
        if kind == "body" and case["body_must_contain"] not in match.get("body", ""):
            raise AssertionError(f"Body evidence missing for {case['id']}")
    elif kind == "call_graph":
        with closing(sqlite3.connect(repo / ".code-index/index.db")) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(proc_call_graph)")]
            rows = [dict(zip(columns, row, strict=True)) for row in connection.execute("SELECT * FROM proc_call_graph")]
        caller = case["caller"].casefold()
        callee = case["callee"].casefold()
        if not any(
            caller in " ".join(str(value) for value in row.values()).casefold()
            and callee in " ".join(str(value) for value in row.values()).casefold()
            for row in rows
        ):
            raise AssertionError(f"Call graph edge missing: {case['caller']} -> {case['callee']}")
    elif kind == "manifest":
        with closing(sqlite3.connect(repo / ".code-index/index.db")) as connection:
            row = connection.execute(
                "SELECT config_version FROM config_manifest WHERE full_name=?",
                (case["full_name"],),
            ).fetchone()
        if row != (case["config_version"],):
            raise AssertionError(f"Manifest evidence mismatch for {case['full_name']}: {row}")
    else:
        raise AssertionError(f"Unsupported evaluation case kind: {kind}")

    citation = assert_citation(repo, case["citation"])
    return {
        "id": case["id"],
        "kind": kind,
        "score": 1,
        "citation": citation,
        "verdict": "PASS",
    }


def render_markdown(report: dict[str, Any]) -> str:
    rows = ["| Case | Kind | Score | Citation |", "|---|---|---:|---|"]
    for case in report["cases"]:
        citation = case["citation"]
        rows.append(
            f"| {case['id']} | {case['kind']} | {case['score']} | " f"`{citation['path']}:{citation['line_start']}` |"
        )
    return (
        "# PRISM-like 1C provider-free evaluation\n\n"
        f"Verdict: **{report['verdict']}**  \n"
        f"Score: **{report['score']}/{report['max_score']}**  \n"
        "Network: **disabled**  \nProvider credentials: **not used**\n\n" + "\n".join(rows) + "\n"
    )


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve()
    fixture = args.fixture.resolve()
    definition = json.loads(args.cases.resolve().read_text(encoding="utf-8"))
    if definition.get("network_required") is not False:
        raise AssertionError("Provider-free suite must explicitly disable network")
    if definition.get("provider_credentials_required") is not False:
        raise AssertionError("Provider-free suite must explicitly disable provider credentials")

    with tempfile.TemporaryDirectory(prefix="1c-ai-prism-eval-") as temp:
        repo = Path(temp) / "fixture"
        shutil.copytree(fixture, repo)
        run(binary, "index", str(repo), "--force")
        cases = [evaluate_case(binary, repo, case) for case in definition["cases"]]

    score = sum(case["score"] for case in cases)
    report = {
        "schema_version": 1,
        "suite": definition["suite"],
        "network_used": False,
        "provider_credentials_used": False,
        "score": score,
        "max_score": len(cases),
        "cases": cases,
        "verdict": "PASS" if score == len(cases) else "FAIL",
    }
    rendered_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    rendered_markdown = render_markdown(report)
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(rendered_json, encoding="utf-8")
    if args.markdown_report:
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_report.write_text(rendered_markdown, encoding="utf-8")
    sys.stdout.buffer.write(rendered_json.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

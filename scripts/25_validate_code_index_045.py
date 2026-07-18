from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PARITY_TABLES = (
    "data_links",
    "metadata_objects",
    "config_manifest",
    "metadata_modules",
    "metadata_forms",
    "role_rights",
    "event_subscriptions",
    "metadata_code_usages",
    "proc_call_graph",
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Deterministic contract gate for code-index-mcp 0.45.x.")
    parser.add_argument(
        "--binary",
        type=Path,
        default=root / "tools/code-index-mcp/target/release/bsl-indexer.exe",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=root / "tests/fixtures/code-index-045",
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def run(binary: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
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
    return result


def database(repo: Path) -> Path:
    path = repo / ".code-index/index.db"
    if not path.is_file():
        raise AssertionError(f"Index database was not created: {path}")
    return path


def semantic_table_digest(repo: Path, table: str) -> tuple[int, str]:
    connection = sqlite3.connect(database(repo))
    try:
        table_info = list(connection.execute(f"PRAGMA table_info({table})"))
        if not table_info:
            raise AssertionError(f"Required table is missing: {table}")
        columns = [row[1] for row in table_info if not (row[5] and row[1] == "id")]
        rows: list[list[Any]] = []
        for row in connection.execute(f"SELECT {','.join(columns)} FROM {table}"):
            normalized: list[Any] = []
            for value in row:
                if isinstance(value, str):
                    value = value.replace(str(repo), "<ROOT>").replace(repo.as_posix(), "<ROOT>")
                normalized.append(value)
            rows.append(normalized)
    finally:
        connection.close()
    rows.sort(key=lambda item: json.dumps(item, ensure_ascii=False, default=str))
    payload = json.dumps(
        {"columns": columns, "rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode()
    return len(rows), hashlib.sha256(payload).hexdigest()


def manifest_rows(repo: Path) -> list[tuple[str, str, str]]:
    connection = sqlite3.connect(database(repo))
    try:
        return list(
            connection.execute("SELECT area, full_name, config_version " "FROM config_manifest ORDER BY area, full_name")
        )
    finally:
        connection.close()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve()
    fixture = args.fixture.resolve()
    if not binary.is_file():
        raise FileNotFoundError(binary)
    if not fixture.is_dir():
        raise FileNotFoundError(fixture)

    version = run(binary, "--version").stdout.strip()
    if version != "code-index 0.45.0":
        raise AssertionError(f"Expected code-index 0.45.0, got {version!r}")

    with tempfile.TemporaryDirectory(prefix="1c-ai-code-index-045-") as temp:
        temp_root = Path(temp)
        incremental = temp_root / "incremental"
        clean_full = temp_root / "clean-full"
        shutil.copytree(fixture, incremental)
        shutil.copytree(fixture, clean_full)

        run(binary, "index", str(incremental), "--force")
        stats = json.loads(run(binary, "stats", "--path", str(incremental), "--json").stdout)
        expected_stats = {
            "total_functions": 2,
            "total_classes": 1,
            "total_calls": 2,
        }
        for key, expected in expected_stats.items():
            if stats.get(key) != expected:
                raise AssertionError(f"Golden stat {key}: expected {expected}, got {stats.get(key)}")

        query = json.loads(
            run(
                binary,
                "query",
                "РассчитатьСумму",
                "--path",
                str(incremental),
                "--language",
                "bsl",
                "--json",
            ).stdout
        )
        functions = query.get("functions", [])
        if len(functions) != 1 or functions[0].get("name") != "РассчитатьСумму":
            raise AssertionError(f"Golden function lookup drifted: {functions}")
        if "Новый Массив" in functions[0].get("body", ""):
            raise AssertionError("Golden function unexpectedly contains another procedure body")

        expected_manifest = [
            ("", "CommonModule.ПилотИндекса", "golden-v1"),
            ("", "CommonModule.ПилотИндекса.Module", ""),
        ]
        actual_manifest = manifest_rows(incremental)
        if actual_manifest != expected_manifest:
            raise AssertionError(f"config_manifest drifted: expected {expected_manifest}, got {actual_manifest}")

        relative_module = Path("CommonModules/ПилотИндекса/Ext/Module.bsl")
        marker = "\n// CODE_INDEX_045_INCREMENTAL_CONTRACT\n"
        for repo in (incremental, clean_full):
            module = repo / relative_module
            module.write_text(module.read_text(encoding="utf-8") + marker, encoding="utf-8")

        run(binary, "index", str(incremental))
        run(binary, "index", str(clean_full), "--force")

        parity: dict[str, dict[str, Any]] = {}
        for table in PARITY_TABLES:
            incremental_digest = semantic_table_digest(incremental, table)
            full_digest = semantic_table_digest(clean_full, table)
            if incremental_digest != full_digest:
                raise AssertionError(
                    f"Incremental/full semantic parity failed for {table}: " f"{incremental_digest} != {full_digest}"
                )
            parity[table] = {
                "rows": incremental_digest[0],
                "sha256": incremental_digest[1],
            }

    report = {
        "schema_version": 1,
        "version": version,
        "golden_stats": stats,
        "manifest_rows": [list(row) for row in expected_manifest],
        "incremental_full_parity": parity,
        "verdict": "PASS",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

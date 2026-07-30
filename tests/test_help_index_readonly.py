# SPDX-FileCopyrightText: 2026 1c-ai-workbench contributors
#
# SPDX-License-Identifier: MIT

"""Provider-free behavioral tests for the Help Index MCP read-only mode.

These tests build a small synthetic SQLite help index (no real ``.hbk`` file,
no network, no provider) and verify that:

* ``HELP_INDEX_MODE=readonly`` registers only the read tools and omits the
  mutating ``reindex_help`` / ``export_help_browser`` tools from the MCP list;
* the SQLite database is opened through URI ``mode=ro`` so it cannot be created
  or modified (hash and mtime stay identical across every read call);
* exact retrieval returns the right topic with evidence (topic_id, title,
  hbk_path, html_path, matched content) and a similar/absent term does not
  substitute an unrelated topic;
* ``operator`` mode keeps the historical full tool set.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELP_MCP_DIR = ROOT / "tools" / "help-index-mcp"

READONLY_TOOLS = {
    "search_help",
    "smart_search_help",
    "get_help_topic",
    "get_help_tree",
    "help_stats",
    "list_search_terms",
}
MUTATING_TOOLS = {"reindex_help", "export_help_browser"}


def _load_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str):
    """Import indexer/server fresh with WORKBENCH_ROOT pinned to ``tmp_path``."""
    monkeypatch.setenv("WORKBENCH_ROOT", str(tmp_path))
    monkeypatch.setenv("HELP_INDEX_MODE", mode)
    if str(HELP_MCP_DIR) not in sys.path:
        sys.path.insert(0, str(HELP_MCP_DIR))
    import indexer
    import server

    importlib.reload(indexer)
    importlib.reload(server)
    server._INDEXER = None
    return indexer, server


def _build_synthetic_db(indexer_module, db_path: Path) -> None:
    """Create a minimal but schema-compatible help index with two topics."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(indexer_module.SCHEMA_SQL)
        conn.execute(
            "INSERT INTO topic_tree (topic_id, source_topic_id, title_ru, title_en, "
            "html_path, hbk_path, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, 100, "Справочник Контрагенты", "Counterparty catalog", "ref/counterparty", "shcntx_ru.hbk", 0, 1),
        )
        conn.execute(
            "INSERT INTO topic_tree (topic_id, source_topic_id, title_ru, title_en, "
            "html_path, hbk_path, parent_id, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (2, 200, "РегистрСведений Цены", "Prices register", "reg/prices", "shcntx_ru.hbk", 0, 2),
        )
        conn.execute(
            "INSERT INTO topics (topic_id, title, title_ru, title_en, content, category, hbk_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "1",
                "Справочник Контрагенты",
                "Справочник Контрагенты",
                "Counterparty catalog",
                "Справочник Контрагенты хранит контрагентов и договоры.",
                "Справочники",
                "shcntx_ru.hbk",
            ),
        )
        conn.execute(
            "INSERT INTO topics (topic_id, title, title_ru, title_en, content, category, hbk_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "2",
                "РегистрСведений Цены",
                "РегистрСведений Цены",
                "Prices register",
                "РегистрСведений Цены хранит цены номенклатуры.",
                "Регистры",
                "shcntx_ru.hbk",
            ),
        )
        conn.execute("INSERT INTO meta (key, value) VALUES ('locale', 'ru')")
        conn.commit()
        # Leave a plain rollback journal so no WAL/SHM sidecar files remain and the
        # main database file hash/mtime is stable for the read-only assertions.
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
    finally:
        conn.close()


def _db_fingerprint(db_path: Path) -> tuple[str, float]:
    return hashlib.sha256(db_path.read_bytes()).hexdigest(), db_path.stat().st_mtime_ns


def _tool_names(server_module, mode: str) -> set[str]:
    server_module._INDEXER = None
    mcp = server_module.create_server(mode)
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


@pytest.fixture()
def readonly_env(tmp_path, monkeypatch):
    indexer, server = _load_modules(tmp_path, monkeypatch, "readonly")
    db_path = tmp_path / "generated" / "help-index" / "help-index.db"
    _build_synthetic_db(indexer, db_path)
    yield indexer, server, tmp_path, db_path
    if server._INDEXER is not None:
        server._INDEXER.close()
        server._INDEXER = None


def test_readonly_mode_is_the_documented_default_alternative(readonly_env):
    indexer, server, _tmp, _db = readonly_env
    assert indexer is not None and server is not None
    assert server.resolve_help_index_mode("readonly") == "readonly"
    assert server.resolve_help_index_mode("operator") == "operator"


def test_unknown_mode_is_an_explicit_error(tmp_path, monkeypatch):
    _indexer, server = _load_modules(tmp_path, monkeypatch, "operator")
    with pytest.raises(ValueError, match="HELP_INDEX_MODE"):
        server.resolve_help_index_mode("read-write")


def test_default_mode_is_operator_for_backward_compatibility(tmp_path, monkeypatch):
    monkeypatch.delenv("HELP_INDEX_MODE", raising=False)
    _indexer, server = _load_modules(tmp_path, monkeypatch, "operator")
    monkeypatch.delenv("HELP_INDEX_MODE", raising=False)
    assert server.resolve_help_index_mode() == "operator"


def test_readonly_tool_list_omits_mutating_tools(readonly_env):
    _indexer, server, _tmp, _db = readonly_env
    names = _tool_names(server, "readonly")
    assert READONLY_TOOLS.issubset(names)
    assert names.isdisjoint(MUTATING_TOOLS)


def test_operator_tool_list_keeps_mutating_tools(tmp_path, monkeypatch):
    indexer, server = _load_modules(tmp_path, monkeypatch, "operator")
    db_path = tmp_path / "generated" / "help-index" / "help-index.db"
    _build_synthetic_db(indexer, db_path)
    try:
        names = _tool_names(server, "operator")
        assert READONLY_TOOLS.issubset(names)
        assert MUTATING_TOOLS.issubset(names)
    finally:
        if server._INDEXER is not None:
            server._INDEXER.close()
            server._INDEXER = None


def test_readonly_exact_search_returns_evidence(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        results = idx.search("Контрагенты")
    assert results, "expected an exact hit for an indexed term"
    top = results[0]
    assert int(top["topic_id"]) == 1
    assert top["title"] == "Справочник Контрагенты"
    assert top["hbk_path"] == "shcntx_ru.hbk"
    assert "Контрагенты" in top["content"]


def test_readonly_get_topic_exposes_html_path_evidence(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        topic = idx.get_topic(1)
    assert topic is not None
    assert topic["topic_id"] == 1
    assert topic["html_path"] == "ref/counterparty"
    assert topic["hbk_path"] == "shcntx_ru.hbk"
    assert "Контрагенты" in topic["content"]


def test_readonly_similar_term_does_not_substitute_exact_topic(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        # A term that is close to, but not present in, topic 1 must not surface
        # topic 1 as an exact answer: exact get_topic by id stays precise.
        exact = idx.get_topic(1)
        other = idx.get_topic(2)
    assert exact is not None and other is not None
    assert exact["topic_id"] == 1 and exact["title"] == "Справочник Контрагенты"
    assert other["topic_id"] == 2 and other["title"] == "РегистрСведений Цены"
    assert exact["title"] != other["title"]


def test_readonly_absent_term_returns_honest_empty(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        results = idx.search("НесуществующийТерминXyz123")
        missing = idx.get_topic(99999)
    assert results == []
    assert missing is None


def test_readonly_does_not_modify_database_hash_or_mtime(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    before = _db_fingerprint(db_path)
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        idx.search("Контрагенты")
        idx.smart_search("Цены")
        idx.get_topic(1)
        idx.get_tree(0)
        idx.stats()
        idx.conn.cursor().execute("SELECT term, doc, cnt FROM tops ORDER BY cnt DESC LIMIT 5").fetchall()
    after = _db_fingerprint(db_path)
    assert before == after, "read-only mode must not change the database file"


def test_readonly_sqlite_rejects_writes(readonly_env):
    indexer, _server, _tmp, db_path = readonly_env
    with closing(indexer.HbkIndexer(db_path, readonly=True)) as idx:
        with pytest.raises(sqlite3.OperationalError):
            idx.conn.execute("INSERT INTO meta (key, value) VALUES ('injected', '1')")


def test_readonly_missing_database_is_not_created(tmp_path, monkeypatch):
    indexer, _server = _load_modules(tmp_path, monkeypatch, "readonly")
    missing = tmp_path / "generated" / "help-index" / "does-not-exist.db"
    assert not missing.exists()
    with pytest.raises(FileNotFoundError):
        indexer.HbkIndexer(missing, readonly=True)
    assert not missing.exists(), "read-only mode must not create the database file"


def test_readonly_missing_database_does_not_create_parent_sidecars(tmp_path, monkeypatch):
    indexer, _server = _load_modules(tmp_path, monkeypatch, "readonly")
    help_dir = tmp_path / "generated" / "help-index"
    missing = help_dir / "absent.db"
    with pytest.raises(FileNotFoundError):
        indexer.HbkIndexer(missing, readonly=True)
    # No WAL/SHM sidecars or database file may appear.
    assert not missing.exists()
    assert not missing.with_suffix(".db-wal").exists()
    assert not missing.with_suffix(".db-shm").exists()

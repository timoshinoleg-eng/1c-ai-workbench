"""
server.py — Help Index MCP сервер для 1C Enterprise .hbk файлов.

Инструменты:
  - reindex_help(path: str, db_path?: str) — проиндексировать .hbk
  - search_help(query: str, limit?: int, locale?: str) — FTS5 поиск
  - smart_search_help(query: str, limit?: int, locale?: str) — prefix fallback поиск
  - get_help_topic(topic_id: int) — контент топика
  - get_help_tree(parent_id?: int) — иерархия TOC
  - help_stats() — статистика индекса
  - list_search_terms() — популярные термины (будущее)
  - export_help_browser(output_path?: str, limit?: int) — статический HTML-браузер
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Конфигурация по умолчанию ─────────────────────────────────────────────

WORKBENCH_ROOT = Path(os.environ.get("WORKBENCH_ROOT", r"C:\1c-ai-workbench")).expanduser().resolve()
DEFAULT_DB_DIR = WORKBENCH_ROOT / "generated" / "help-index"
DEFAULT_DB = DEFAULT_DB_DIR / "help-index.db"


def _default_hbk_dir() -> Path:
    configured = os.environ.get("HBK_DIR")
    if configured:
        return Path(configured).expanduser()
    platform_root = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "1cv8t"
    candidates = sorted(platform_root.glob(r"*\bin"), reverse=True)
    for candidate in candidates:
        if list(candidate.glob("*.hbk")) or list(candidate.glob("*.HBK")):
            return candidate
    return platform_root


DEFAULT_HBK_DIR = _default_hbk_dir()


# ── JSON helpers ───────────────────────────────────────────────────────────


def ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2)


def err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg}, ensure_ascii=False, indent=2)


# ── Lazy loader ────────────────────────────────────────────────────────────


_INDEXER = None


def _get_indexer(db_path: str | None = None) -> HbkIndexer:  # noqa: F821
    """Ленивый импорт + инициализация индексера."""
    from indexer import HbkIndexer, resolve_workbench_path

    global _INDEXER
    if db_path is None and _INDEXER is not None:
        return _INDEXER
    path = resolve_workbench_path(db_path or DEFAULT_DB, "db_path")
    if _INDEXER is None or _INDEXER.db_path != path:
        if _INDEXER:
            _INDEXER.close()
        _INDEXER = HbkIndexer(path)
    return _INDEXER


# ── MCP сервер ─────────────────────────────────────────────────────────────


try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore


def create_server() -> FastMCP:
    """Создать и сконфигурировать MCP сервер."""
    if FastMCP is None:
        raise ImportError("fastmcp not installed. Run: pip install fastmcp>=3.0.0")

    mcp = FastMCP(
        "1c-help-index",
        instructions="Index and search 1C Enterprise .hbk help files. "
        "Topics indexed from .hbk binary containers into SQLite FTS5 for full-text search.",
    )

    # ── инструменты ────────────────────────────────────────────────────────

    @mcp.tool()
    def reindex_help(path: str, db_path: str | None = None) -> str:
        """
        Проиндексировать .hbk файл(ы).

        Args:
            path: Путь к .hbk файлу или директории с .hbk файлами
            db_path: (опционально) путь к SQLite БД индекса
        """
        from indexer import HbkIndexer, resolve_workbench_path

        indexer = None
        try:
            target = Path(path).expanduser().resolve(strict=False)
            if not target.exists():
                return err(f"Path not found: {path}")

            hbk_files: list[Path] = []
            if target.is_file() and target.suffix.lower() == ".hbk":
                hbk_files.append(target)
            elif target.is_dir():
                hbk_files.extend(target.glob("*.hbk"))
                hbk_files.extend(target.glob("*.HBK"))
            else:
                return err(f"Not a .hbk file: {path}")

            if not hbk_files:
                return err(f"No .hbk files found in {path}")

            hbk_files = sorted(set(hbk_files), key=lambda p: str(p).lower())
            db = resolve_workbench_path(db_path or DEFAULT_DB, "db_path")
            indexer = HbkIndexer(db)
            results = []
            for hbk in hbk_files:
                try:
                    count = indexer.index_hbk(hbk)
                    results.append({"file": str(hbk), "topics": count})
                except Exception as e:
                    logger.error("Failed to index %s: %s", hbk, e)
                    results.append({"file": str(hbk), "error": str(e)})

            global _INDEXER
            if _INDEXER is not None and _INDEXER is not indexer:
                _INDEXER.close()
            _INDEXER = indexer
            indexer = None
            return ok({"db_path": str(db), "indexed": len(hbk_files), "results": results})
        except Exception as e:
            return err(f"Reindex failed: {e}")
        finally:
            if indexer is not None:
                indexer.close()

    @mcp.tool()
    def search_help(query: str, limit: int = 20, locale: str | None = None) -> str:
        """
        Полнотекстовый поиск по индексу справки 1С.

        Args:
            query: Поисковый запрос (FTS5 синтаксис)
            limit: Максимум результатов (по умолч. 20)
            locale: Фильтр по локали ("ru", "en")
        """
        try:
            results = _get_indexer().search(query, limit=limit, locale=locale)
            return ok(
                {
                    "query": query,
                    "count": len(results),
                    "results": results,
                }
            )
        except Exception as e:
            return err(f"Search failed: {e}")

    @mcp.tool()
    def smart_search_help(query: str, limit: int = 20, locale: str | None = None) -> str:
        """
        Поиск по справке с prefix fallback.

        Args:
            query: Пользовательский поисковый запрос
            limit: Максимум результатов
            locale: Фильтр по локали ("ru", "en")
        """
        try:
            results = _get_indexer().smart_search(query, limit=limit, locale=locale)
            return ok(
                {
                    "query": query,
                    "count": len(results),
                    "results": results,
                }
            )
        except Exception as e:
            return err(f"Smart search failed: {e}")

    @mcp.tool()
    def get_help_topic(topic_id: int) -> str:
        """
        Получить полный контент топика справки.

        Args:
            topic_id: ID топика из результатов поиска
        """
        try:
            topic = _get_indexer().get_topic(topic_id)
            if topic is None:
                return err(f"Topic {topic_id} not found")
            return ok(topic)
        except Exception as e:
            return err(f"Get topic failed: {e}")

    @mcp.tool()
    def get_help_tree(parent_id: int = 0) -> str:
        """
        Получить иерархию разделов справки.

        Args:
            parent_id: ID родительского раздела (0 = корень)
        """
        try:
            children = _get_indexer().get_tree(parent_id)
            return ok(
                {
                    "parent_id": parent_id,
                    "count": len(children),
                    "children": children,
                }
            )
        except Exception as e:
            return err(f"Tree query failed: {e}")

    @mcp.tool()
    def help_stats() -> str:
        """Статистика проиндексированных данных."""
        try:
            return ok(_get_indexer().stats())
        except Exception as e:
            return err(f"Stats failed: {e}")

    @mcp.tool()
    def list_search_terms() -> str:
        """
        Список уникальных терминов в индексе (через FTS5 vocab).

        Note: the FTS5 vocab table is created idempotently during schema init.
        """
        try:
            indexer = _get_indexer()
            cur = indexer.conn.cursor()
            rows = cur.execute("SELECT term, doc, cnt FROM tops ORDER BY cnt DESC LIMIT 100").fetchall()
            return ok({"terms": [{"term": r[0], "docs": r[1], "occurrences": r[2]} for r in rows]})
        except Exception as e:
            return err(f"List search terms failed: {e}")

    @mcp.tool()
    def export_help_browser(output_path: str | None = None, limit: int = 5000) -> str:
        """
        Экспортировать статический HTML-браузер справки.

        Args:
            output_path: Путь к HTML. По умолчанию generated/help-index/help-browser.html
            limit: Максимум топиков в статическом списке
        """
        try:
            from indexer import resolve_workbench_path

            target = resolve_workbench_path(output_path or DEFAULT_DB_DIR / "help-browser.html", "output_path")
            return ok(_get_indexer().export_browser(target, limit=limit))
        except Exception as e:
            return err(f"Browser export failed: {e}")

    return mcp


# ── run ────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")

    # Проверка зависимостей
    try:
        from mcp.server.fastmcp import FastMCP  # noqa
    except ImportError:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp>=3.0.0")
        sys.exit(1)

    server = create_server()
    logger.info("Starting 1c-help-index MCP server...")
    server.run()


if __name__ == "__main__":
    main()

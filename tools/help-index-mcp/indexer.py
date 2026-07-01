"""
indexer.py — Построитель SQLite FTS5 индекса для .hbk файлов.

Извлекает TOC + HTML из .hbk, строит поисковый индекс.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from html import unescape as html_unescape
from pathlib import Path

from hbk_parser import (
    open_filestorage,
    open_hbk,
    read_toc_text,
)
from toc_parser import Chunk, parse_toc

logger = logging.getLogger(__name__)

WORKBENCH_ROOT = Path(os.environ.get("WORKBENCH_ROOT", Path(__file__).resolve().parents[2])).expanduser().resolve()

# ── константы ──────────────────────────────────────────────────────────────

TOPIC_TREE_SCHEMA = """
CREATE TABLE topic_tree (
    topic_id    INTEGER PRIMARY KEY,
    source_topic_id INTEGER NOT NULL DEFAULT 0,
    title_ru    TEXT NOT NULL DEFAULT '',
    title_en    TEXT NOT NULL DEFAULT '',
    html_path   TEXT NOT NULL DEFAULT '',
    hbk_path    TEXT NOT NULL DEFAULT '',
    parent_id   INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
)
"""

TOPICS_SCHEMA = """
CREATE VIRTUAL TABLE topics USING fts5(
    topic_id UNINDEXED,
    title,
    title_ru,
    title_en,
    content,
    category UNINDEXED,
    hbk_path UNINDEXED,
    tokenize='unicode61 remove_diacritics 2',
    prefix='2,3'
)
"""

SCHEMA_SQL = """
-- Таблица иерархии
CREATE TABLE IF NOT EXISTS topic_tree (
    topic_id    INTEGER PRIMARY KEY,
    source_topic_id INTEGER NOT NULL DEFAULT 0,
    title_ru    TEXT NOT NULL DEFAULT '',
    title_en    TEXT NOT NULL DEFAULT '',
    html_path   TEXT NOT NULL DEFAULT '',
    hbk_path    TEXT NOT NULL DEFAULT '',
    parent_id   INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_topic_tree_parent ON topic_tree(parent_id);
CREATE INDEX IF NOT EXISTS idx_topic_tree_hbk ON topic_tree(hbk_path);

-- FTS5 поисковый индекс
CREATE VIRTUAL TABLE IF NOT EXISTS topics USING fts5(
    topic_id UNINDEXED,
    title,
    title_ru,
    title_en,
    content,
    category UNINDEXED,
    hbk_path UNINDEXED,
    tokenize='unicode61 remove_diacritics 2',
    prefix='2,3'
);

CREATE VIRTUAL TABLE IF NOT EXISTS tops USING fts5vocab(topics, 'row');

-- Версия и метаданные
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


# ── модели ─────────────────────────────────────────────────────────────────


@dataclass
class Topic:
    """Одна тема для индексации."""

    topic_id: int
    title_ru: str
    title_en: str
    html_path: str
    html_content: str
    category: str
    source_topic_id: int = 0
    hbk_path: str = ""
    parent_id: int = 0


# ── HTML-парсер (минимальный) ──────────────────────────────────────────────


# Теги, которые заменяются на разделители слов (не удаляются целиком)
_BLOCK_TAGS = re.compile(
    r"</?(?:p|br|div|h[1-6]|li|tr|td|th|blockquote|pre|section|article|header|footer)>",
    re.IGNORECASE,
)
# Теги, которые полностью удаляются вместе с содержимым
_STRIP_TAGS = re.compile(
    r"<(style|script|svg|iframe|object|embed|canvas|noscript|video|audio|math|form)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
# Оставшиеся HTML теги
_HTML_TAG = re.compile(r"<[^>]+>")
# Множественные пробелы и переводы строк
_WHITESPACE = re.compile(r"\s+")
# Специфичные символы HTML
_HTML_ENTITIES = {"\xa0": " "}


def resolve_workbench_path(path_value: str | Path, label: str = "path") -> Path:
    target = Path(path_value).expanduser()
    if not target.is_absolute():
        target = WORKBENCH_ROOT / target
    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(WORKBENCH_ROOT)
    except ValueError as exc:
        raise PermissionError(f"{label} must stay under WORKBENCH_ROOT: {resolved}") from exc
    return resolved


def strip_html(html: str) -> str:
    """
    Извлечь чистый текст из HTML.
    - Удаляет активные/встраиваемые блоки целиком
    - Заменяет блочные теги на пробелы
    - Удаляет остальные теги
    - Заменяет HTML-сущности
    - Схлопывает пробелы
    """
    # удаляем стили/скрипты
    text = _STRIP_TAGS.sub("", html)
    # заменяем блочные теги на пробелы
    text = _BLOCK_TAGS.sub(" ", text)
    # удаляем остальные теги
    text = _HTML_TAG.sub("", text)
    # HTML-сущности
    text = html_unescape(text)
    for ent, char in _HTML_ENTITIES.items():
        text = text.replace(ent, char)
    # схлопываем пробелы
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def extract_title_from_html(html: str) -> str:
    """Извлечь <title> из HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return strip_html(m.group(1))
    # fallback: первый <h1>
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return strip_html(m.group(1))
    return ""


# ── извлечение локали ─────────────────────────────────────────────────────


def detect_locale(hbk_path: str) -> str:
    """
    Определить локаль по имени файла.
    shcntx_ru.hbk → "ru", shcntx_root.hbk → "en"
    """
    stem = Path(hbk_path).stem
    parts = stem.split("_")
    if len(parts) >= 2:
        locale = parts[-1]
        if locale in ("ru", "en", "uk", "fr", "de"):
            return locale
    return "en"


def _hbk_storage_key(hbk_path: Path) -> str:
    return str(hbk_path.resolve(strict=False))


# ── индексер ──────────────────────────────────────────────────────────────


class HbkIndexer:
    """Построитель FTS5 индекса из .hbk файла(ов)."""

    def __init__(self, db_path: str | Path):
        self.db_path = resolve_workbench_path(db_path, "db_path")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=OFF")
        self._init_schema()

    def _init_schema(self):
        self.conn.execute(TOPIC_TREE_SCHEMA.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
        self.conn.execute(TOPICS_SCHEMA.replace("CREATE VIRTUAL TABLE", "CREATE VIRTUAL TABLE IF NOT EXISTS", 1))
        self.conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self._migrate_schema()
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_tree_parent ON topic_tree(parent_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_tree_hbk ON topic_tree(hbk_path)")
        self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS tops USING fts5vocab(topics, 'row')")
        self.conn.commit()

    def _migrate_schema(self):
        topic_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(topics)").fetchall()}
        required_topic_columns = {
            "topic_id",
            "title",
            "title_ru",
            "title_en",
            "content",
            "category",
            "hbk_path",
        }
        topic_sql_row = self.conn.execute("SELECT sql FROM sqlite_master WHERE name = 'topics'").fetchone()
        topic_sql = topic_sql_row[0] if topic_sql_row else ""
        tree_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(topic_tree)").fetchall()}
        required_tree_columns = {
            "topic_id",
            "source_topic_id",
            "title_ru",
            "title_en",
            "html_path",
            "hbk_path",
            "parent_id",
            "sort_order",
        }

        topic_schema_outdated = topic_columns and (
            not required_topic_columns.issubset(topic_columns)
            or "remove_diacritics 2" not in topic_sql
            or "prefix='2,3'" not in topic_sql
        )
        tree_schema_outdated = tree_columns and not required_tree_columns.issubset(tree_columns)

        if topic_schema_outdated or tree_schema_outdated:
            logger.warning("Rebuilding outdated help-index schema")
            self.conn.execute("DROP TABLE IF EXISTS tops")
            self.conn.execute("DROP TABLE IF EXISTS topics")
            self.conn.execute("DROP TABLE IF EXISTS topic_tree")
            self.conn.execute(TOPIC_TREE_SCHEMA)
            self.conn.execute(TOPICS_SCHEMA)
            self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS tops USING fts5vocab(topics, 'row')")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_tree_parent ON topic_tree(parent_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_tree_hbk ON topic_tree(hbk_path)")

    def index_hbk(self, hbk_path: str | Path) -> int:
        """
        Индексировать один .hbk файл.
        Возвращает количество проиндексированных топиков.
        """
        hbk_path = Path(hbk_path).expanduser().resolve(strict=False)
        hbk_key = _hbk_storage_key(hbk_path)
        if not hbk_path.exists():
            raise FileNotFoundError(f"HBK file not found: {hbk_path}")

        logger.info("Indexing %s...", hbk_path.name)
        container = open_hbk(hbk_path)

        # TOC
        toc_text = read_toc_text(container)
        if not toc_text:
            logger.warning("No TOC in %s", hbk_path.name)
            return 0
        chunks = parse_toc(toc_text)
        logger.info("Parsed %d TOC chunks", len(chunks))

        # FileStorage
        zf = open_filestorage(container)
        if not zf:
            logger.warning("No readable FileStorage ZIP in %s; indexing TOC only", hbk_path.name)

        # locale
        locale = detect_locale(str(hbk_path))

        cur = self.conn.cursor()
        hbk_keys_to_replace = sorted({hbk_key, hbk_path.name})
        placeholders = ",".join("?" for _ in hbk_keys_to_replace)
        existing_topic_ids: dict[int, int] = {
            int(row[0]): int(row[1])
            for row in cur.execute(
                f"SELECT source_topic_id, topic_id FROM topic_tree WHERE hbk_path IN ({placeholders})",
                hbk_keys_to_replace,
            ).fetchall()
        }
        for key in hbk_keys_to_replace:
            self._delete_hbk(cur, key)
        start_topic_id = self._next_topic_id(cur)
        local_to_topic_id: dict[int, int] = {}
        next_topic_id = start_topic_id + 1
        for c in chunks:
            if c.id in existing_topic_ids:
                local_to_topic_id[c.id] = existing_topic_ids[c.id]
            else:
                while next_topic_id in local_to_topic_id.values():
                    next_topic_id += 1
                local_to_topic_id[c.id] = next_topic_id
                next_topic_id += 1

        # chunk id → chunk
        chunk_map: dict[int, Chunk] = {c.id: c for c in chunks}

        topics: list[Topic] = []

        # Обходим все чанки, для каждого достаём HTML, парсим
        for c in chunks:
            topic_id = local_to_topic_id[c.id]
            html_path = c.html_path
            html_content = _read_html(zf, html_path) if zf and html_path else ""
            clean_text = strip_html(html_content) if html_content else ""

            # Извлекаем заголовок из HTML если в TOC названия пустые
            title_ru = c.name_ru
            title_en = c.name_en
            if not title_ru and not title_en and html_content:
                title_from_html = extract_title_from_html(html_content)
                if locale == "ru":
                    title_ru = title_from_html
                else:
                    title_en = title_from_html

            # Категория = имя родительского раздела (первый предок с именем)
            category = _get_category(c, chunk_map)

            topics.append(
                Topic(
                    topic_id=topic_id,
                    title_ru=title_ru,
                    title_en=title_en,
                    html_path=html_path,
                    html_content=clean_text,
                    category=category,
                    source_topic_id=c.id,
                    hbk_path=hbk_key,
                    parent_id=local_to_topic_id.get(c.parent_id, 0),
                )
            )

        # INSERT в БД
        self._insert_topics(topics, hbk_key, locale)
        if zf:
            zf.close()

        logger.info("Indexed %d topics from %s", len(topics), hbk_path.name)
        return len(topics)

    def _delete_hbk(self, cur: sqlite3.Cursor, hbk_path: str):
        cur.execute("DELETE FROM topics WHERE hbk_path = ?", (hbk_path,))
        cur.execute("DELETE FROM topic_tree WHERE hbk_path = ?", (hbk_path,))

    def _next_topic_id(self, cur: sqlite3.Cursor) -> int:
        row = cur.execute("SELECT COALESCE(MAX(topic_id), 0) FROM topic_tree").fetchone()
        return int(row[0] or 0)

    def _insert_topics(self, topics: list[Topic], hbk_path: str, locale: str):
        """Вставить топики в БД."""
        cur = self.conn.cursor()

        # topic_tree
        cur.executemany(
            "INSERT OR REPLACE INTO topic_tree "
            "(topic_id, source_topic_id, title_ru, title_en, html_path, hbk_path, parent_id, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    t.topic_id,
                    t.source_topic_id,
                    t.title_ru,
                    t.title_en,
                    t.html_path,
                    t.hbk_path,
                    t.parent_id,
                    t.topic_id,
                )
                for t in topics
            ],
        )

        # FTS5 topics
        for t in topics:
            title = t.title_ru or t.title_en
            content = t.html_content
            category = t.category

            cur.execute(
                "INSERT INTO topics (topic_id, title, title_ru, title_en, content, category, hbk_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(t.topic_id),
                    title,
                    t.title_ru,
                    t.title_en,
                    content,
                    category,
                    hbk_path,
                ),
            )

        # meta
        cur.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("hbk_path", hbk_path),
        )
        cur.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("locale", locale),
        )
        cur.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("topic_count", str(len(topics))),
        )

        self.conn.commit()

    def search(self, query: str, limit: int = 20, locale: str | None = None) -> list[dict]:
        """
        Поиск по FTS5 индексу.
        Возвращает список словарей с ключами: topic_id, title, content, category, hbk_path, rank.
        """
        cur = self.conn.cursor()

        if locale == "ru":
            rank_expr = "bm25(topics, 0.0, 1.4, 2.0, 1.0, 1.0, 0.0, 0.0)"
        elif locale == "en":
            rank_expr = "bm25(topics, 0.0, 1.4, 1.0, 2.0, 1.0, 0.0, 0.0)"
        else:
            rank_expr = "bm25(topics, 0.0, 1.4, 1.5, 1.5, 1.0, 0.0, 0.0)"

        sql = f"""
        SELECT t.topic_id, t.title, t.title_ru, t.title_en, t.content, t.category, t.hbk_path, {rank_expr} as rank
        FROM topics t
        WHERE topics MATCH ?
        """

        params: list[str] = [query]
        if locale:
            locale = locale.lower()
            if locale == "en":
                sql += " AND (lower(t.hbk_path) LIKE ? OR lower(t.hbk_path) LIKE ?)"
                params.extend(["%_en.hbk", "%_root.hbk"])
            else:
                sql += " AND lower(t.hbk_path) LIKE ?"
                params.append(f"%_{locale}.hbk")

        sql += " ORDER BY rank LIMIT ?"
        params.append(str(limit))

        rows = cur.execute(sql, params).fetchall()
        return [
            {
                "topic_id": r[0],
                "title": r[1],
                "title_ru": r[2],
                "title_en": r[3],
                "content": r[4][:500] if r[4] else "",
                "category": r[5] or "",
                "hbk_path": r[6],
                "rank": round(r[7], 4),
            }
            for r in rows
        ]

    def smart_search(self, query: str, limit: int = 20, locale: str | None = None) -> list[dict]:
        """
        Поиск в стиле обычного веб-поиска: точный FTS5 запрос, затем prefix fallback.
        FTS5 prefix='2,3' ускоряет token* запросы, но не превращает обычный MATCH в prefix search.
        """
        results = self.search(query, limit=limit, locale=locale)
        if len(results) >= limit:
            return results

        prefix_query = _to_prefix_query(query)
        if not prefix_query or prefix_query == query:
            return results

        seen = {str(r["topic_id"]) for r in results}
        for row in self.search(prefix_query, limit=limit, locale=locale):
            if str(row["topic_id"]) in seen:
                continue
            results.append(row)
            seen.add(str(row["topic_id"]))
            if len(results) >= limit:
                break
        return results

    def get_topic(self, topic_id: int) -> dict | None:
        """Получить полную информацию о топике."""
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT t.topic_id, t.title, t.content, t.category, t.hbk_path, "
            "       t.title_ru, t.title_en, tt.html_path, tt.parent_id "
            "FROM topics t "
            "JOIN topic_tree tt ON tt.topic_id = t.topic_id "
            "WHERE t.topic_id = ?",
            (str(topic_id),),
        ).fetchone()
        if not row:
            return None
        return {
            "topic_id": int(row[0]),
            "title": row[1],
            "content": row[2],
            "category": row[3] or "",
            "hbk_path": row[4],
            "title_ru": row[5],
            "title_en": row[6],
            "html_path": row[7],
            "parent_id": row[8],
        }

    def get_tree(self, parent_id: int = 0) -> list[dict]:
        """Получить дочерние элементы иерархии."""
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT topic_id, title_ru, title_en, html_path, parent_id, hbk_path, source_topic_id "
            "FROM topic_tree WHERE parent_id = ? "
            "ORDER BY sort_order",
            (parent_id,),
        ).fetchall()
        return [
            {
                "topic_id": r[0],
                "title_ru": r[1],
                "title_en": r[2],
                "html_path": r[3],
                "parent_id": r[4],
                "hbk_path": r[5],
                "source_topic_id": r[6],
            }
            for r in rows
        ]

    def stats(self) -> dict:
        """Статистика индекса."""
        cur = self.conn.cursor()
        topic_count = cur.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
        tree_count = cur.execute("SELECT COUNT(*) FROM topic_tree").fetchone()[0]
        file_count = cur.execute("SELECT COUNT(DISTINCT hbk_path) FROM topics").fetchone()[0]
        hbk_paths = [row[0] for row in cur.execute("SELECT DISTINCT hbk_path FROM topics ORDER BY hbk_path").fetchall()]
        locale = cur.execute("SELECT value FROM meta WHERE key='locale'").fetchone()
        return {
            "topics": topic_count,
            "tree_nodes": tree_count,
            "indexed_files": file_count,
            "hbk_path": hbk_paths[0] if file_count == 1 and hbk_paths else None,
            "hbk_paths": hbk_paths,
            "locale": locale[0] if locale else None,
        }

    def export_browser(self, output_path: str | Path, limit: int = 5000) -> dict:
        """Экспортировать простой статический HTML-браузер индекса."""
        output_path = resolve_workbench_path(output_path, "output_path")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT topic_id, title, title_ru, title_en, category, hbk_path "
            "FROM topics ORDER BY hbk_path, CAST(topic_id AS INTEGER) LIMIT ?",
            (limit,),
        ).fetchall()

        items = "\n".join(
            '        <li data-title="{data_title}" data-category="{data_category}" data-file="{data_file}">'
            '<a href="#" data-topic="{topic_id}">{title}</a>'
            "<small>{category} · {hbk_path}</small></li>".format(
                topic_id=_html_escape(str(r[0])),
                title=_html_escape(r[2] or r[3] or r[1] or f"Topic {r[0]}"),
                category=_html_escape(r[4] or ""),
                hbk_path=_html_escape(r[5] or ""),
                data_title=_html_escape(" ".join(str(v or "") for v in (r[1], r[2], r[3])).lower()),
                data_category=_html_escape(str(r[4] or "").lower()),
                data_file=_html_escape(str(r[5] or "").lower()),
            )
            for r in rows
        )

        html = _BROWSER_TEMPLATE.format(items=items, count=len(rows))
        output_path.write_text(html, encoding="utf-8")
        return {"output_path": str(output_path), "topics_exported": len(rows)}

    def close(self):
        self.conn.close()


# ── утилиты ────────────────────────────────────────────────────────────────


def _read_html(zf: zipfile.ZipFile, html_path: str) -> str:
    """Прочитать HTML файл из ZIP-архива FileStorage."""
    # В FileStorage имена файлов без ведущего / и без .html
    candidates = [html_path]
    if html_path.startswith("/"):
        candidates.append(html_path.lstrip("/"))
    else:
        candidates.append("/" + html_path)

    # Без расширения — так хранятся в FileStorage
    for key in candidates:
        key = key.lstrip("/")
        try:
            return zf.read(key).decode("utf-8", errors="replace")
        except KeyError:
            pass

    logger.debug("HTML not found in FileStorage: %s", html_path)
    return ""


def _get_category(chunk: Chunk, chunk_map: dict[int, Chunk]) -> str:
    """Определить категорию: найти ближайшего предка с именем."""
    seen: set[int] = set()
    current_id = chunk.parent_id
    while current_id != 0 and current_id not in seen:
        seen.add(current_id)
        parent = chunk_map.get(current_id)
        if parent is None:
            break
        name = parent.display_name
        if name:
            return name
        current_id = parent.parent_id
    return ""


_FTS_TOKEN = re.compile(r"[\w\u0400-\u04FF]{2,}", re.UNICODE)


def _to_prefix_query(query: str) -> str:
    tokens = _FTS_TOKEN.findall(query.lower())
    if not tokens:
        return ""
    return " ".join(f"{token}*" for token in tokens)


def _html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


_BROWSER_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>1C Help Index Browser</title>
  <style>
    body {{ margin: 0; font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; color: #1f2937; background: #f8fafc; }}
    header {{ position: sticky; top: 0; padding: 14px 18px; background: #ffffff; border-bottom: 1px solid #d7dee8; }}
    h1 {{ margin: 0 0 10px; font-size: 18px; }}
    input {{ width: min(760px, calc(100vw - 36px)); padding: 9px 11px; border: 1px solid #b8c2cf; border-radius: 6px; }}
    main {{ padding: 14px 18px 28px; }}
    ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }}
    li {{ padding: 9px 11px; background: #ffffff; border: 1px solid #d7dee8; border-radius: 6px; }}
    a {{ color: #0f5f9c; text-decoration: none; font-weight: 600; }}
    small {{ display: block; margin-top: 3px; color: #64748b; }}
    .meta {{ margin: 8px 0 0; color: #64748b; }}
  </style>
</head>
<body>
  <header>
    <h1>1C Help Index Browser</h1>
    <input id="filter" type="search" placeholder="Фильтр по заголовку, категории или .hbk файлу" autofocus>
    <div class="meta"><span id="visible">{count}</span> / {count} topics</div>
  </header>
  <main>
    <ul id="topics">
{items}
    </ul>
  </main>
  <script>
    const filter = document.getElementById('filter');
    const visible = document.getElementById('visible');
    const rows = Array.from(document.querySelectorAll('#topics li'));
    filter.addEventListener('input', () => {{
      const q = filter.value.trim().toLowerCase();
      let count = 0;
      for (const row of rows) {{
        const haystack = `${{row.dataset.title}} ${{row.dataset.category}} ${{row.dataset.file}}`;
        const match = !q || haystack.includes(q);
        row.style.display = match ? '' : 'none';
        if (match) count += 1;
      }}
      visible.textContent = count;
    }});
  </script>
</body>
</html>
"""


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    import sys

    if len(sys.argv) < 3:
        print("Usage: python indexer.py <index.db> <file.hbk> [file2.hbk ...]")
        sys.exit(1)

    db_path = sys.argv[1]
    hbk_files = sys.argv[2:]

    indexer = HbkIndexer(db_path)
    total = 0
    for hbk in hbk_files:
        try:
            total += indexer.index_hbk(hbk)
        except Exception as e:
            logger.error("Failed to index %s: %s", hbk, e)

    logger.info("Total indexed: %d topics in %s", total, db_path)
    print(f"\nStats: {indexer.stats()}")
    indexer.close()


if __name__ == "__main__":
    main()

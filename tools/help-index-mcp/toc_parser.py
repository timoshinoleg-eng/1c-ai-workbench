"""
toc_parser.py — Парсер TOC (Table of Contents) текста .hbk файлов.

Токенизирует и разбирает TOC текст из PackBlock сущности.
Формат (tokenized text):
  {chunkCount
    {id parentId childCount childId1... {props} {nameContainer} "htmlPath"}
    ...
  }

См. alkoleft/hbk-viewer (Tokenizer.kt, TocParser.kt).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

BOM = "\ufeff"


# ── модели ─────────────────────────────────────────────────────────────────


@dataclass
class NameObject:
    """Имя на одном языке."""

    language_code: str  # "ru", "en"
    name: str


@dataclass
class PropertiesContainer:
    """Свойства чанка — имена + путь к HTML."""

    name_objects: list[NameObject] = field(default_factory=list)
    html_path: str = ""


@dataclass
class Chunk:
    """Элемент оглавления."""

    id: int
    parent_id: int
    child_ids: list[int]
    properties: PropertiesContainer

    @property
    def name_en(self) -> str:
        for no in self.properties.name_objects:
            if no.language_code in ("en", "#"):
                return no.name
        return ""

    @property
    def name_ru(self) -> str:
        for no in self.properties.name_objects:
            if no.language_code in ("ru", "#"):
                return no.name
        return ""

    @property
    def display_name(self) -> str:
        """Приоритет: RU, затем EN."""
        return self.name_ru or self.name_en or ""

    @property
    def html_path(self) -> str:
        return self.properties.html_path


@dataclass
class TocRecord:
    """Иерархическая запись TOC для индексации."""

    title_ru: str = ""
    title_en: str = ""
    html_path: str = ""
    children: list[TocRecord] = field(default_factory=list)


# ── токенизатор ────────────────────────────────────────────────────────────


def tokenize(content: str) -> list[str]:
    """
    Разбить TOC текст на токены.

    Правила:
    - BOM (\ufeff) игнорируется
    - Строки в кавычках — один токен (с кавычками)
    - "" внутри строки = экранированная кавычка
    - { } и запятые — отдельные токены
    - Пробелы — разделители
    - Пустые токены и запятые отфильтровываются
    """
    tokens: list[str] = []
    current = []
    in_string = False
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == BOM:
            i += 1
            continue

        if ch == '"':
            if in_string:
                # проверка экранирования ""
                if i + 1 < len(content) and content[i + 1] == '"':
                    current.append('"')
                    i += 1
                else:
                    current.append(ch)
                    tokens.append("".join(current))
                    current = []
                    in_string = False
            else:
                if current:
                    tokens.append("".join(current).strip())
                    current = []
                current.append(ch)
                in_string = True

        elif in_string:
            current.append(ch)

        elif ch in ("{", "}", ","):
            if current:
                tokens.append("".join(current).strip())
                current = []
            tokens.append(ch)

        elif ch.isspace():
            if current:
                tokens.append("".join(current).strip())
                current = []

        else:
            current.append(ch)

        i += 1

    if current:
        tokens.append("".join(current).strip())

    # фильтр
    return [t for t in tokens if t and t != ","]


# ── PeekableIterator ──────────────────────────────────────────────────────


class PeekableIterator:
    """Итератор с поддержкой peek()."""

    def __init__(self, tokens: list[str]):
        self._tokens = tokens
        self._pos = 0

    def has_next(self) -> bool:
        return self._pos < len(self._tokens)

    def peek(self) -> str | None:
        if not self.has_next():
            return None
        return self._tokens[self._pos]

    def next(self) -> str:
        if not self.has_next():
            raise StopIteration("No more tokens")
        val = self._tokens[self._pos]
        self._pos += 1
        return val


# ── парсер TOC ────────────────────────────────────────────────────────────


def parse_toc(toc_text: str) -> list[Chunk]:
    """
    Разобрать TOC текст в список Chunk.
    """
    tokens = tokenize(toc_text)
    it = PeekableIterator(tokens)
    return _parse_table_of_content(it)


def _parse_table_of_content(it: PeekableIterator[str]) -> list[Chunk]:
    """{ chunkCount chunk1 chunk2 ... }"""
    _expect(it, "{")
    _parse_number(it)  # chunkCount — игнорируем, мы просто собираем всё
    chunks: list[Chunk] = []
    while it.has_next() and it.peek() != "}":
        chunks.append(_parse_chunk(it))
    _expect(it, "}")
    return chunks


def _parse_chunk(it: PeekableIterator[str]) -> Chunk:
    """{ id parentId childCount childId1...childIdN properties }"""
    _expect(it, "{")
    chunk_id = _parse_number(it)
    parent_id = _parse_number(it)
    child_count = _parse_number(it)
    child_ids = []
    for _ in range(child_count):
        child_ids.append(_parse_number(it))
    properties = _parse_properties_container(it)
    _expect(it, "}")
    logger.debug(
        "Chunk id=%d parent=%d children=%d html=%s",
        chunk_id,
        parent_id,
        len(child_ids),
        properties.html_path,
    )
    return Chunk(id=chunk_id, parent_id=parent_id, child_ids=child_ids, properties=properties)


def _parse_properties_container(it: PeekableIterator[str]) -> PropertiesContainer:
    """{ number1 number2 nameContainer htmlPath }"""
    _expect(it, "{")
    _parse_number(it)  # number1 (неизвестного назначения)
    _parse_number(it)  # number2 (неизвестного назначения)
    name_container = _parse_name_container(it)
    html_path = _parse_string(it)
    _expect(it, "}")
    return PropertiesContainer(name_objects=name_container, html_path=html_path)


def _parse_name_container(it: PeekableIterator[str]) -> list[NameObject]:
    """{ number1 number2 nameObject1 [nameObject2] }"""
    _expect(it, "{")
    _parse_number(it)  # number1
    _parse_number(it)  # number2
    objects: list[NameObject] = []
    while it.has_next() and it.peek() != "}":
        objects.append(_parse_name_object(it))
    _expect(it, "}")
    return objects


def _parse_name_object(it: PeekableIterator[str]) -> NameObject:
    """{"langCode" "name"}"""
    _expect(it, "{")
    lang_code = _parse_string(it)
    name = _parse_string(it)
    _expect(it, "}")
    return NameObject(language_code=lang_code, name=name)


def _parse_number(it: PeekableIterator[str]) -> int:
    token = it.next()
    try:
        return int(token)
    except ValueError:
        raise ValueError(f"Expected number, got '{token}'")


def _parse_string(it: PeekableIterator[str]) -> str:
    token = it.next()
    if not (token.startswith('"') and token.endswith('"')):
        raise ValueError(f"Expected quoted string, got '{token}'")
    return token[1:-1]


def _expect(it: PeekableIterator[str], expected: str):
    token = it.next()
    if token != expected:
        raise ValueError(f"Expected '{expected}', got '{token}'")


# ── построитель иерархии ──────────────────────────────────────────────────


def build_tree(chunks: list[Chunk]) -> list[TocRecord]:
    """
    Построить иерархическое дерево TocRecord из плоского списка Chunk.
    Корни = chunk-ы с parent_id == 0 (или отсутствием родителя).
    """
    # группируем по parent_id
    children_map: dict[int, list[Chunk]] = {}
    for c in chunks:
        children_map.setdefault(c.parent_id, []).append(c)

    # находим корни: parent_id == 0 или parent_id не существует в списке
    all_ids = {c.id for c in chunks}
    roots = [c for c in chunks if c.parent_id == 0 or c.parent_id not in all_ids]

    def _build(chunk: Chunk) -> TocRecord:
        rec = TocRecord(
            title_ru=chunk.name_ru,
            title_en=chunk.name_en,
            html_path=chunk.html_path,
        )
        for child_chunk in children_map.get(chunk.id, []):
            rec.children.append(_build(child_chunk))
        return rec

    return [_build(root) for root in roots]


def print_tree(records: list[TocRecord], indent: int = 0):
    """Распечатать дерево TOC для отладки."""
    prefix = "  " * indent
    for rec in records:
        title = rec.title_ru or rec.title_en or "(no name)"
        path = f" [{rec.html_path}]" if rec.html_path else ""
        print(f"{prefix}- {title}{path}")
        print_tree(rec.children, indent + 1)


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("Usage: python toc_parser.py <toc_text_file>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()

    chunks = parse_toc(text)
    print(f"\n── Parsed {len(chunks)} chunks ──\n")

    # первые 10 чанков
    for c in chunks[:10]:
        names = [(no.language_code, no.name) for no in c.properties.name_objects]
        print(f"  id={c.id} parent={c.parent_id} names={names} html={c.html_path}")

    # дерево
    tree = build_tree(chunks)
    print(f"\n── Tree ({len(tree)} roots) ──")
    print_tree(tree)


if __name__ == "__main__":
    main()

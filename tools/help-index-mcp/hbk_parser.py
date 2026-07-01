"""
hbk_parser.py — Бинарный контейнер HBK (Help Book) для 1С:Предприятие.

Читает .hbk файлы: заголовок контейнера, TOC блок, цепочки блоков сущностей.
Извлекает: PackBlock (ZIP с TOC), FileStorage (ZIP с HTML), Book (метаданные).

Формат описан: https://github.com/alkoleft/hbk-viewer
"""

from __future__ import annotations

import io
import logging
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── константы ──────────────────────────────────────────────────────────────
SPLITTER = 0x7FFFFFFF  # Int.MAX_VALUE
BLOCK_HEADER_MIN = 31  # \r\n + hex8 + ' ' + hex8 + ' ' + hex8 + ' ' + \r\n

ENTITY_PACKBLOCK = "PackBlock"
ENTITY_FILESTORAGE = "FileStorage"
ENTITY_BOOK = "Book"


# ── модели ─────────────────────────────────────────────────────────────────


@dataclass
class ContainerHeader:
    """16-байтовый заголовок контейнера."""

    free_block_addr: int
    default_block_size: int
    entity_count: int
    reserved: int


@dataclass
class BlockHeader:
    """Заголовок блока данных (CRLF + hex поля + CRLF)."""

    length: int  # полная длина заголовка в байтах
    payload_size: int  # размер полезных данных в байте
    block_size: int  # общий размер блока (включая заголовок)
    next_block: int  # адрес следующего блока (0 = конец цепочки)


@dataclass
class FileInfo:
    """Запись в TOC блоке: адрес заголовка + тела сущности."""

    header_addr: int
    body_addr: int


@dataclass
class Entity:
    """Извлечённая сущность контейнера."""

    name: str
    data: bytes


@dataclass
class Container:
    """Полностью разобранный HBK контейнер."""

    header: ContainerHeader
    entities: dict[str, Entity] = field(default_factory=dict)

    def get(self, name: str) -> bytes | None:
        ent = self.entities.get(name)
        return ent.data if ent else None

    def get_packblock(self) -> bytes | None:
        """PackBlock — ZIP-архив с текстом TOC."""
        return self.get(ENTITY_PACKBLOCK)

    def get_filestorage(self) -> bytes | None:
        """FileStorage — ZIP-архив с HTML-страницами."""
        return self.get(ENTITY_FILESTORAGE)

    def get_book(self) -> bytes | None:
        """Book — UTF-8 текст метаданных."""
        return self.get(ENTITY_BOOK)


# ── низкоуровневый парсинг блоков ──────────────────────────────────────────


def _read_int32_le(data: bytes, offset: int) -> int:
    """Прочитать INT32 little-endian из data[offset:]."""
    return struct.unpack_from("<i", data, offset)[0]


def _parse_hex8(data: bytes, offset: int) -> int:
    """Прочитать 8-символьное hex-поле как int (с поддержкой > 0x7FFFFFFF)."""
    s = data[offset : offset + 8].decode("ascii", errors="replace").strip()
    if not s:
        raise ValueError(f"Empty hex field at offset {offset}")
    # поддержка FFFFFFFF → -1 как signed 32-bit
    val = int(s, 16)
    if val >= 0x80000000:
        val -= 0x100000000
    return val


def _read_block_header(data: bytes, offset: int) -> BlockHeader:
    """Прочитать заголовок блока, начиная с offset (должен быть \r\n)."""
    if offset <= 0 or offset + BLOCK_HEADER_MIN > len(data):
        raise ValueError(f"Block header offset out of range: {offset}")
    if data[offset] != 0x0D or data[offset + 1] != 0x0A:
        raise ValueError(f"Invalid block header at offset {offset}: expected \\r\\n")
    pos = offset + 2

    # payload_size (8 hex + space)
    if data[pos + 8] != 0x20:
        raise ValueError(f"Expected space after payload_size at offset {pos + 8}")
    payload_size = _parse_hex8(data, pos)
    pos += 9

    # block_size (8 hex + space)
    if data[pos + 8] != 0x20:
        raise ValueError(f"Expected space after block_size at offset {pos + 8}")
    block_size = _parse_hex8(data, pos)
    pos += 9

    # next_block (8 hex + space)
    if data[pos + 8] != 0x20:
        raise ValueError(f"Expected space after next_block at offset {pos + 8}")
    next_block = _parse_hex8(data, pos)
    pos += 9

    # завершающий CRLF
    if data[pos] != 0x0D or data[pos + 1] != 0x0A:
        raise ValueError(f"Expected trailing \\r\\n in block header at offset {pos}")
    pos += 2

    length = pos - offset
    return BlockHeader(
        length=length,
        payload_size=payload_size,
        block_size=block_size,
        next_block=next_block,
    )


def _read_block_chain(data: bytes, start_addr: int) -> bytes:
    """
    Прочитать цепочку блоков, начиная с start_addr.

    Соответствует ContainerReader.kt readBlockContent:
      - Первый блок: payload_size = общий размер данных во всей цепочке.
      - Каждый блок: читается min(block_size, remaining) байт.
      - Цепочка следует по next_block (0/SPLITTER = конец).
    """
    if start_addr <= 0 or start_addr >= SPLITTER or start_addr + BLOCK_HEADER_MIN > len(data):
        return b""

    first_hdr = _read_block_header(data, start_addr)
    total_size = first_hdr.payload_size
    if total_size == 0:
        return b""

    result = bytearray(total_size)
    offset = 0
    addr = start_addr

    while addr > 0 and addr < SPLITTER and offset < total_size:
        if addr + BLOCK_HEADER_MIN > len(data):
            raise ValueError(f"Block chain offset out of range: {addr}")
        hdr = _read_block_header(data, addr)
        chunk_size = min(hdr.block_size, total_size - offset)
        payload_start = addr + hdr.length
        result[offset : offset + chunk_size] = data[payload_start : payload_start + chunk_size]
        offset += chunk_size

        if hdr.next_block <= 0 or hdr.next_block >= SPLITTER:
            break
        addr = hdr.next_block

    return bytes(result)


# ── парсинг контейнера ─────────────────────────────────────────────────────


def parse_container(data: bytes) -> Container:
    """
    Разобрать .hbk файл из bytes → Container.
    """
    # 1. Заголовок контейнера (16 байт)
    header = ContainerHeader(
        free_block_addr=_read_int32_le(data, 0),
        default_block_size=_read_int32_le(data, 4),
        entity_count=_read_int32_le(data, 8),
        reserved=_read_int32_le(data, 12),
    )
    logger.debug(
        "Container header: free_block=%d default_block=%d entities=%d reserved=%d",
        header.free_block_addr,
        header.default_block_size,
        header.entity_count,
        header.reserved,
    )

    # 2. TOC блок (начинается с offset 16)
    toc_header = _read_block_header(data, 16)
    file_info_count = toc_header.payload_size // 12
    logger.debug(
        "TOC block: payload=%d file_info_count=%d",
        toc_header.payload_size,
        file_info_count,
    )

    # 3. Парсим FileInfo записи
    toc_data_start = 16 + toc_header.length
    files: list[FileInfo] = []
    for i in range(file_info_count):
        off = toc_data_start + i * 12
        head_addr = _read_int32_le(data, off)
        body_addr = _read_int32_le(data, off + 4)
        reserved = _read_int32_le(data, off + 8)
        if reserved != SPLITTER:
            logger.warning(
                "FileInfo[%d] has unexpected reserved value 0x%08X",
                i,
                reserved & 0xFFFFFFFF,
            )
        files.append(FileInfo(header_addr=head_addr, body_addr=body_addr))

    # 4. Извлекаем сущности
    entities: dict[str, Entity] = {}
    for fi in files:
        # Читаем имя из заголовочного блока
        name = _read_entity_name(data, fi.header_addr)
        # Читаем тело из цепочки блоков
        body = _read_block_chain(data, fi.body_addr)
        entities[name] = Entity(name=name, data=body)
        logger.debug(
            "Entity '%s': header=0x%X body=0x%X size=%d",
            name,
            fi.header_addr,
            fi.body_addr,
            len(body),
        )

    return Container(header=header, entities=entities)


def _read_entity_name(data: bytes, header_addr: int) -> str:
    """
    Прочитать имя сущности из заголовочного блока.

    Формат (ContainerReader.kt readFileName):
      payload[0:4]   — entity number (INT32 LE)
      payload[4:20]  — unknown (3 × INT32 LE + delimiter \0\0\0\0)
      payload[20:-4] — имя в UTF-16LE
      payload[-4:]   — неизвестный хвост (обычно \0\0\0\0)
    """
    hdr = _read_block_header(data, header_addr)
    name_end = header_addr + hdr.length + hdr.payload_size
    payload = data[header_addr + hdr.length : name_end]
    name_raw = payload[20:-4] if len(payload) > 24 else b""
    return name_raw.decode("utf-16-le", errors="replace").strip("\0").strip()


# ── высокоуровневые читатели ──────────────────────────────────────────────


def open_hbk(path: str | Path) -> Container:
    """Открыть .hbk файл и разобрать контейнер."""
    path = Path(path)
    data = path.read_bytes()
    logger.info("Opened %s: %d bytes", path.name, len(data))
    return parse_container(data)


def read_toc_text(container: Container) -> str | None:
    """
    Извлечь текст TOC из PackBlock.
    PackBlock — ZIP-архив, внутри 1 файл с TOC в UTF-8.
    """
    raw = container.get_packblock()
    if not raw:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            if not names:
                return None
            # Берём первый (и единственный) файл в архиве
            return zf.read(names[0]).decode("utf-8")
    except zipfile.BadZipFile:
        for encoding in ("utf-8", "utf-16-le", "cp1251"):
            text = raw.decode(encoding, errors="replace").strip("\ufeff\x00\r\n\t ")
            if text:
                return text
        return None


def open_filestorage(container: Container) -> zipfile.ZipFile | None:
    """
    Открыть FileStorage как ZipFile.
    Возвращает ZipFile или None, если сущности нет.
    """
    raw = container.get_filestorage()
    if raw is None:
        return None
    try:
        return zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        logger.debug("FileStorage entity is not a ZIP archive")
        return None


def read_book_meta(container: Container) -> str | None:
    """
    Прочитать Book метаданные как UTF-8 строку.
    """
    raw = container.get_book()
    if raw is None:
        return None
    return raw.decode("utf-8").strip()


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("Usage: python hbk_parser.py <file.hbk>")
        sys.exit(1)
    path = Path(sys.argv[1])
    container = open_hbk(path)

    print(f"\n── Container: {path.name} ──")
    print(f"  Entities: {list(container.entities.keys())}")

    for name, ent in container.entities.items():
        print(f"\n  [{name}] {len(ent.data)} bytes")
        if name == ENTITY_PACKBLOCK:
            toc_text = read_toc_text(container)
            if toc_text:
                print(f"    TOC length: {len(toc_text)} chars")
                print(f"    First 300 chars:\n{toc_text[:300]}")
        elif name == ENTITY_FILESTORAGE:
            zf = open_filestorage(container)
            if zf:
                file_list = zf.namelist()
                print(f"    Files in ZIP: {len(file_list)}")
                for f in file_list[:10]:
                    print(f"      {f}")
                if len(file_list) > 10:
                    print(f"      ... and {len(file_list) - 10} more")
        elif name == ENTITY_BOOK:
            meta = read_book_meta(container)
            print(f"    Book meta:\n      {meta}")


if __name__ == "__main__":
    main()

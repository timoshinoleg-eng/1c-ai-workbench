from __future__ import annotations

import importlib
import sys
import warnings
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_BRIDGE_ROOT = REPO_ROOT / "tools" / "skills-bridge"


@pytest.fixture(scope="module")
def common_module():
    sys.path.insert(0, str(SKILLS_BRIDGE_ROOT))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module("tools.common")


def _import_safe_read_text():
    sys.path.insert(0, str(SKILLS_BRIDGE_ROOT))
    import tools.common as common

    return common.safe_read_text


def _import_path_within_root():
    sys.path.insert(0, str(SKILLS_BRIDGE_ROOT))
    import tools.common as common

    return common.path_within_root


class TestSafeReadText:
    """Regression tests for the cp1251 / utf-8 auto-detection chain.

    1C production code is overwhelmingly saved as cp1251 on Russian-language
    installations. A utf-8-only read silently corrupts Cyrillic to U+FFFD
    and breaks every downstream parser and search index.
    """

    def test_reads_cp1251_cyrillic(self, tmp_path: Path) -> None:
        safe_read_text = _import_safe_read_text()
        sample = (
            "Процедура РассчитатьСумму(Знач Сумма)\n"
            "    Возврат Сумма * 1.20;\n"
            "КонецПроцедуры\n"
        )
        f = tmp_path / "Module.bsl"
        f.write_bytes(sample.encode("cp1251"))
        result = safe_read_text(f)
        assert "Процедура" in result
        assert "РассчитатьСумму" in result
        assert "\ufffd" not in result

    def test_reads_utf8_sig(self, tmp_path: Path) -> None:
        safe_read_text = _import_safe_read_text()
        sample = "// comment\nПроцедура Тест()\nКонецПроцедуры\n"
        f = tmp_path / "Module.bsl"
        f.write_bytes(sample.encode("utf-8-sig"))
        result = safe_read_text(f)
        assert "Процедура Тест" in result
        assert "\ufeff" not in result  # BOM stripped

    def test_reads_plain_utf8(self, tmp_path: Path) -> None:
        safe_read_text = _import_safe_read_text()
        sample = "Процедура Тест() КонецПроцедуры\n"
        f = tmp_path / "Module.bsl"
        f.write_bytes(sample.encode("utf-8"))
        result = safe_read_text(f)
        assert "Процедура" in result

    def test_falls_back_to_replace_on_garbage(self, tmp_path: Path) -> None:
        safe_read_text = _import_safe_read_text()
        f = tmp_path / "Module.bsl"
        f.write_bytes(b"\xff\xfe\x00\x01garbage")
        result = safe_read_text(f)
        assert isinstance(result, str)


class TestPathWithinRoot:
    """The path-traversal guard around the source-mirror boundary."""

    def test_rejects_path_outside_root(self, tmp_path: Path) -> None:
        path_within_root = _import_path_within_root()
        root = tmp_path / "mirror"
        root.mkdir()
        outside = tmp_path / "outside.xml"
        outside.write_text("<root/>")
        assert path_within_root(outside, root) is None

    def test_rejects_dotdot_traversal(self, tmp_path: Path) -> None:
        path_within_root = _import_path_within_root()
        root = tmp_path / "mirror"
        root.mkdir()
        escape = root / ".." / "etc" / "passwd"
        assert path_within_root(escape, root) is None

    def test_accepts_path_inside_root(self, tmp_path: Path) -> None:
        path_within_root = _import_path_within_root()
        root = tmp_path / "mirror"
        root.mkdir()
        inside = root / "Catalogs" / "Sales.xml"
        inside.parent.mkdir()
        inside.write_text("<root/>")
        result = path_within_root(inside, root)
        assert result is not None
        assert result.is_file()

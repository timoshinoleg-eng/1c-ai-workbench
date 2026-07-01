from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

WORKBENCH_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_PATHS = (
    WORKBENCH_ROOT / "generated" / "index" / "source-mirror",
    WORKBENCH_ROOT / "generated" / "extract",
)

METADATA_DIRS = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "CommonModules": "CommonModule",
    "Reports": "Report",
    "DataProcessors": "DataProcessor",
    "ExternalReports": "ExternalReport",
    "ExternalDataProcessors": "ExternalDataProcessor",
    "AccumulationRegisters": "AccumulationRegister",
    "InformationRegisters": "InformationRegister",
    "AccountingRegisters": "AccountingRegister",
    "CalculationRegisters": "CalculationRegister",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "Enums": "Enum",
    "Roles": "Role",
    "Subsystems": "Subsystem",
    "Constants": "Constant",
    "BusinessProcesses": "BusinessProcess",
    "Tasks": "Task",
    "ExchangePlans": "ExchangePlan",
    "DefinedTypes": "DefinedType",
    "HTTPServices": "HTTPService",
    "WebServices": "WebService",
    "ScheduledJobs": "ScheduledJob",
    "EventSubscriptions": "EventSubscription",
}


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourcePathArgs(ToolArgs):
    source_path: str | None = Field(
        default=None,
        description="Optional source-mirror root. Explicit value wins over SOURCE_MIRROR and generated/index/source-mirror.",
    )


@dataclass(frozen=True)
class TimedResult:
    started: float

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


def timer() -> TimedResult:
    return TimedResult(time.perf_counter())


def result_json(tool: str, ok: bool, data: dict[str, Any], elapsed_ms: int) -> str:
    payload = {
        "tool": tool,
        "ok": ok,
        "elapsed_ms": elapsed_ms,
        **data,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def error_json(tool: str, exc: Exception, elapsed_ms: int) -> str:
    if isinstance(exc, ValidationError):
        message = exc.errors()
    else:
        message = str(exc)
    return result_json(tool, False, {"error": message}, elapsed_ms)


def resolve_source_root(source_path: str | None = None) -> Path:
    candidates: list[Path] = []
    if source_path:
        resolved_source = Path(source_path).expanduser().resolve()
        if path_within_root(resolved_source, WORKBENCH_ROOT) is None:
            raise PermissionError(f"source_path must be inside workbench root: {source_path}")
        candidates.append(resolved_source)
    env_path = os.environ.get("SOURCE_MIRROR") or os.environ.get("ONEC_SOURCE_MIRROR")
    if env_path:
        resolved_env = Path(env_path).expanduser().resolve()
        if path_within_root(resolved_env, WORKBENCH_ROOT) is None:
            raise PermissionError(f"SOURCE_MIRROR must be inside workbench root: {env_path}")
        candidates.append(resolved_env)
    candidates.extend(DEFAULT_SOURCE_PATHS)

    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
    rendered = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"source-mirror root not found. Checked: {rendered}")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def text_of(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def descendant_text(node: ET.Element, descendant_name: str) -> str:
    """Return stripped text of the first descendant (any depth) matching ``descendant_name``.

    Note: this traverses ALL descendants via ``node.iter()``. For direct children only,
    use ``direct_child_text``. The name intentionally reflects descendant semantics
    (was previously called ``child_text`` which was misleading).
    """
    for child in node.iter():
        if local_name(child.tag) == descendant_name and child.text:
            return child.text.strip()
    return ""


def direct_child_text(node: ET.Element, child_name: str) -> str:
    for child in list(node):
        if local_name(child.tag) == child_name and child.text:
            return child.text.strip()
    return ""


def parse_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def path_within_root(path: Path, root: Path) -> Path | None:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def object_type_from_path(path: Path, root: Path) -> str:
    try:
        first = path.relative_to(root).parts[0]
    except ValueError:
        return "Unknown"
    return METADATA_DIRS.get(first, first)


def iter_metadata_xml(root: Path, path_glob: str | None = None) -> Iterable[Path]:
    if path_glob:
        patterns = [
            path_glob,
            f"{path_glob}.xml" if not path_glob.endswith(".xml") else path_glob,
        ]
        seen: set[Path] = set()
        for pattern in patterns:
            for path in root.glob(pattern):
                safe_path = path_within_root(path, root)
                if safe_path and safe_path.is_file() and safe_path.suffix.lower() == ".xml" and safe_path not in seen:
                    seen.add(safe_path)
                    yield safe_path
        return

    for path in root.rglob("*.xml"):
        safe_path = path_within_root(path, root)
        if not safe_path:
            continue
        rel = relative_path(safe_path, root)
        if "/Ext/" in rel or rel.endswith("Rights.xml") or rel.endswith("Form.xml"):
            continue
        yield safe_path


def resolve_xml_path(root: Path, value: str, preferred_dirs: tuple[str, ...] = ()) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return path_within_root(candidate, root)

    direct = (root / value).resolve()
    if path_within_root(direct, root) and direct.exists() and direct.is_file():
        return direct
    if direct.suffix.lower() != ".xml":
        direct_xml = direct.with_suffix(".xml")
        if path_within_root(direct_xml, root) and direct_xml.exists():
            return direct_xml
        nested_xml = direct / f"{direct.name}.xml"
        if path_within_root(nested_xml, root) and nested_xml.exists():
            return nested_xml

    name = candidate.stem if candidate.suffix else candidate.name
    search_dirs = preferred_dirs or tuple(METADATA_DIRS.keys())
    for directory in search_dirs:
        path = root / directory / f"{name}.xml"
        safe_path = path_within_root(path, root)
        if safe_path and safe_path.exists():
            return safe_path
        nested = root / directory / name / f"{name}.xml"
        safe_nested = path_within_root(nested, root)
        if safe_nested and safe_nested.exists():
            return safe_nested
    matches = [
        path for path in (path_within_root(match, root) for match in root.rglob(f"{name}.xml")) if path and path.is_file()
    ]
    return matches[0] if matches else None


def resolve_bsl_path(root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return path_within_root(candidate, root)
    direct = (root / value).resolve()
    if path_within_root(direct, root) and direct.exists() and direct.is_file():
        return direct
    if direct.suffix.lower() != ".bsl":
        direct_bsl = direct.with_suffix(".bsl")
        if path_within_root(direct_bsl, root) and direct_bsl.exists():
            return direct_bsl
    matches = [path for path in (path_within_root(match, root) for match in root.rglob(value)) if path and path.is_file()]
    if matches:
        return matches[0]
    name = candidate.name
    matches = [
        safe_path
        for safe_path in (path_within_root(path, root) for path in root.rglob("*.bsl"))
        if safe_path and safe_path.is_file() and (safe_path.name == name or safe_path.stem == name)
    ]
    return matches[0] if matches else None


def resolve_existing_path(root: Path, value: str, suffix: str = ".xml") -> Path | None:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return path_within_root(candidate, root)
    direct = (root / value).resolve()
    if path_within_root(direct, root) and direct.exists():
        return direct
    if suffix and direct.suffix.lower() != suffix.lower():
        with_suffix = direct.with_suffix(suffix)
        if path_within_root(with_suffix, root) and with_suffix.exists():
            return with_suffix
    normalized_value = value.replace("\\", "/").strip("/")
    if "/" in normalized_value:
        matches = [
            safe_path
            for path in root.rglob(f"*{suffix}" if suffix else "*")
            for safe_path in [path_within_root(path, root)]
            if safe_path and normalized_value.lower() in safe_path.relative_to(root).as_posix().lower()
        ]
    else:
        name = candidate.stem if candidate.suffix else candidate.name
        pattern = f"{name}{suffix}" if suffix else name
        matches = [
            path for path in (path_within_root(match, root) for match in root.rglob(pattern)) if path and path.exists()
        ]
    return matches[0] if matches else None


def collect_named_children(root: ET.Element, names: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for node in root.iter():
        tag = local_name(node.tag)
        if tag not in names:
            continue
        props = next(
            (child for child in list(node) if local_name(child.tag) == "Properties"),
            node,
        )
        name = direct_child_text(props, "Name") or node.attrib.get("name", "")
        if not name:
            continue
        rows.append(
            {
                "kind": tag,
                "name": name,
                "synonym": descendant_text(props, "content"),
                "type": first_type(props),
            }
        )
    return rows


def first_type(node: ET.Element) -> str:
    for item in node.iter():
        if local_name(item.tag) in {"Type", "TypeDescription"} and item.text:
            return item.text.strip()
    for item in node.iter():
        if local_name(item.tag) == "Type" and list(item):
            values = [text_of(child) for child in item.iter() if text_of(child)]
            return ", ".join(values[:3])
    return ""


def top_properties(root: ET.Element) -> dict[str, str]:
    props: dict[str, str] = {}
    properties = next((node for node in root.iter() if local_name(node.tag) == "Properties"), None)
    if properties is None:
        return props
    for child in list(properties):
        key = local_name(child.tag)
        if key in {"Name", "Synonym", "Comment"}:
            continue
        value = text_of(child)
        if value:
            props[key] = value
        if len(props) >= 20:
            break
    return props


def xml_summary(path: Path, source_root: Path) -> dict[str, Any]:
    root = parse_xml(path)
    object_node = next(
        (node for node in root.iter() if node is not root and "uuid" in node.attrib),
        root,
    )
    props = next(
        (node for node in object_node.iter() if local_name(node.tag) == "Properties"),
        object_node,
    )
    child_rows = collect_named_children(
        object_node,
        {
            "Attribute",
            "TabularSection",
            "Form",
            "Command",
            "Resource",
            "Dimension",
            "Requisite",
            "EnumValue",
        },
    )
    by_kind: dict[str, int] = {}
    for row in child_rows:
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    return {
        "name": direct_child_text(props, "Name") or path.stem,
        "type": object_type_from_path(path, source_root),
        "path": relative_path(path, source_root),
        "uuid": object_node.attrib.get("uuid", ""),
        "synonym": descendant_text(props, "content"),
        "properties": top_properties(object_node),
        "children_count": by_kind,
        "children": child_rows,
    }


def markdown_table(headers: list[str], rows: list[list[Any]], limit: int = 50) -> str:
    visible = rows[:limit]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in visible:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    if len(rows) > limit:
        lines.append(f"| ... | {len(rows) - limit} more | |")
    return "\n".join(lines)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


BSL_SIGNATURE_RE = re.compile(
    r"^\s*(?P<kind>Процедура|Функция|Procedure|Function)\s+"
    r"(?P<name>[A-Za-zА-Яа-я_][\wА-Яа-я]*)\s*\((?P<params>[^)]*)\)\s*(?P<export>Экспорт|Export)?",
    re.IGNORECASE | re.MULTILINE,
)


def extract_bsl_symbols(text: str) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for match in BSL_SIGNATURE_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        params = [item.strip() for item in match.group("params").split(",") if item.strip()]
        symbols.append(
            {
                "kind": match.group("kind"),
                "name": match.group("name"),
                "params": params,
                "export": bool(match.group("export")),
                "line": line,
                "signature": match.group(0).strip(),
            }
        )
    return symbols


def safe_read_text(path: Path) -> str:
    """Read a BSL / text file with encoding auto-detection.

    Order:
    1. utf-8-sig (BOM-prefixed, strict)
    2. utf-8 (strict; modern cross-platform 1C:EDT saves)
    3. cp1251 (legacy Russian Windows 1C:Enterprise, common in production)
    4. utf-8 with replacement (last resort, never crashes)

    The chain is strict-first because cp1251 is a 1-byte encoding that
    accepts any byte and would silently mis-decode utf-8 files.
    (sec-fix-2026-06-23)

    Known limitation: a file that mixes encodings within its content
    (e.g., a partial utf-8 region inside an otherwise cp1251 file) cannot
    be detected and will be mis-decoded by whichever codec succeeds first.
    Real 1C dumps do not exhibit this; tools that produce or transform
    1C files are expected to use a single encoding per file.
    """
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

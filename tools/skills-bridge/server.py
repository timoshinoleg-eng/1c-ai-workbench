from __future__ import annotations

from fastmcp import FastMCP

from tools import audit_metadata as audit_metadata_tool
from tools import cf_info as cf_info_tool
from tools import cfe_diff as cfe_diff_tool
from tools import compare_versions as compare_versions_tool
from tools import explain_module as explain_module_tool
from tools import find_object as find_object_tool
from tools import find_similar as find_similar_tool
from tools import form_info as form_info_tool
from tools import form_validate as form_validate_tool
from tools import meta_info as meta_info_tool
from tools import meta_validate as meta_validate_tool
from tools import mxl_info as mxl_info_tool
from tools import query_optimizer as query_optimizer_tool
from tools import role_info as role_info_tool
from tools import skd_info as skd_info_tool
from tools import subsystem_info as subsystem_info_tool
from tools.common import error_json, timer

mcp = FastMCP(
    name="1c-skills",
    instructions=(
        "Read-only MCP bridge for 1C:Enterprise source-mirror analysis. "
        "All tools return JSON strings and never modify the configuration dump."
    ),
)


async def _safe(tool_name: str, runner, **kwargs: object) -> str:
    started = timer()
    try:
        return await runner(**kwargs)
    except Exception as exc:
        return error_json(tool_name, exc, started.elapsed_ms())


@mcp.tool()
async def find_object(
    name: str,
    path_glob: str | None = None,
    limit: int = 20,
    source_path: str | None = None,
) -> str:
    """RU: Найти объект метаданных 1С. EN: Find a 1C metadata object in source-mirror."""
    return await _safe(
        "find_object",
        find_object_tool.run,
        name=name,
        path_glob=path_glob,
        limit=limit,
        source_path=source_path,
    )


@mcp.tool()
async def find_similar(path: str, limit: int = 10, source_path: str | None = None) -> str:
    """RU: Найти похожие BSL-модули. EN: Find similar BSL modules by symbols and text fingerprint."""
    return await _safe(
        "find_similar",
        find_similar_tool.run,
        path=path,
        limit=limit,
        source_path=source_path,
    )


@mcp.tool()
async def audit_metadata(limit: int = 100, source_path: str | None = None) -> str:
    """RU: Аудит метаданных: дубли, пустые синонимы, пустые объекты. EN: Audit metadata dump."""
    return await _safe("audit_metadata", audit_metadata_tool.run, limit=limit, source_path=source_path)


@mcp.tool()
async def compare_versions(left_path: str, right_path: str, limit: int = 200) -> str:
    """RU: Сравнить две версии source-mirror по SHA-256 снимкам файлов. EN: Compare source-mirror versions by file hashes."""
    return await _safe(
        "compare_versions",
        compare_versions_tool.run,
        left_path=left_path,
        right_path=right_path,
        limit=limit,
    )


@mcp.tool()
async def explain_module(path: str, include_calls: bool = True, source_path: str | None = None) -> str:
    """RU: Объяснить BSL-модуль: процедуры, функции, экспорты, вызовы. EN: Explain a BSL module."""
    return await _safe(
        "explain_module",
        explain_module_tool.run,
        path=path,
        include_calls=include_calls,
        source_path=source_path,
    )


@mcp.tool()
async def query_optimizer(query: str) -> str:
    """RU: Найти рискованные паттерны в тексте запроса 1С. EN: Analyze a 1C query for risky patterns."""
    return await _safe("query_optimizer", query_optimizer_tool.run, query=query)


@mcp.tool()
async def meta_info(
    object_path: str,
    mode: str = "overview",
    name: str | None = None,
    source_path: str | None = None,
) -> str:
    """RU: Сводка объекта метаданных. EN: Summarize metadata object structure."""
    return await _safe(
        "meta_info",
        meta_info_tool.run,
        object_path=object_path,
        mode=mode,
        name=name,
        source_path=source_path,
    )


@mcp.tool()
async def skd_info(path: str, limit: int = 200, source_path: str | None = None) -> str:
    """RU: Анализ СКД: наборы, поля, параметры, варианты. EN: Inspect data composition schema nodes."""
    return await _safe("skd_info", skd_info_tool.run, path=path, limit=limit, source_path=source_path)


@mcp.tool()
async def form_info(form_path: str, limit: int = 150, source_path: str | None = None) -> str:
    """RU: Сводка управляемой формы: элементы, реквизиты, команды. EN: Summarize managed form XML."""
    return await _safe(
        "form_info",
        form_info_tool.run,
        form_path=form_path,
        limit=limit,
        source_path=source_path,
    )


@mcp.tool()
async def role_info(role: str, limit: int = 200, source_path: str | None = None) -> str:
    """RU: Сводка роли и Rights.xml. EN: Summarize role metadata and rights file."""
    return await _safe("role_info", role_info_tool.run, role=role, limit=limit, source_path=source_path)


@mcp.tool()
async def cf_info(
    mode: str = "overview",
    section: str | None = None,
    limit: int = 150,
    source_path: str | None = None,
) -> str:
    """RU: Анализ конфигурации 1С — свойства, состав, счётчики. EN: Analyze 1C configuration structure."""
    return await _safe(
        "cf_info",
        cf_info_tool.run,
        mode=mode,
        section=section,
        limit=limit,
        source_path=source_path,
    )


@mcp.tool()
async def cfe_diff(
    extension_path: str,
    config_path: str,
    mode: str = "A",
    source_path: str | None = None,
) -> str:
    """RU: Diff расширения с базовой конфигурацией. EN: Compare CFE with base configuration."""
    return await _safe(
        "cfe_diff",
        cfe_diff_tool.run,
        extension_path=extension_path,
        config_path=config_path,
        mode=mode,
        source_path=source_path,
    )


@mcp.tool()
async def meta_validate(
    object_path: str,
    detailed: bool = False,
    max_errors: int = 30,
    source_path: str | None = None,
) -> str:
    """RU: Валидация объекта метаданных. EN: Validate metadata object XML."""
    return await _safe(
        "meta_validate",
        meta_validate_tool.run,
        object_path=object_path,
        detailed=detailed,
        max_errors=max_errors,
        source_path=source_path,
    )


@mcp.tool()
async def form_validate(
    form_path: str,
    detailed: bool = False,
    max_errors: int = 30,
    source_path: str | None = None,
) -> str:
    """RU: Валидация управляемой формы. EN: Validate managed form XML."""
    return await _safe(
        "form_validate",
        form_validate_tool.run,
        form_path=form_path,
        detailed=detailed,
        max_errors=max_errors,
        source_path=source_path,
    )


@mcp.tool()
async def subsystem_info(
    subsystem_path: str,
    mode: str = "overview",
    name: str | None = None,
    limit: int = 150,
    source_path: str | None = None,
) -> str:
    """RU: Анализ структуры подсистемы. EN: Analyze subsystem structure."""
    return await _safe(
        "subsystem_info",
        subsystem_info_tool.run,
        subsystem_path=subsystem_path,
        mode=mode,
        name=name,
        limit=limit,
        source_path=source_path,
    )


@mcp.tool()
async def mxl_info(
    template_path: str,
    format: str = "text",
    with_text: bool = False,
    max_params: int = 10,
    limit: int = 150,
    source_path: str | None = None,
) -> str:
    """RU: Анализ макета MXL. EN: Analyze MXL template structure."""
    return await _safe(
        "mxl_info",
        mxl_info_tool.run,
        template_path=template_path,
        format=format,
        with_text=with_text,
        max_params=max_params,
        limit=limit,
        source_path=source_path,
    )


if __name__ == "__main__":
    mcp.run()

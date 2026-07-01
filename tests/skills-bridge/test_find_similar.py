from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_find_similar_success(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "find_similar",
        {"source_path": str(source_mirror), "path": "CommonModules/Accounting/Ext/Module.bsl"},
    )
    assert payload["ok"] is True
    assert payload["matches"]
    assert payload["matches"][0]["path"].endswith("Module.bsl")


async def test_find_similar_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "find_similar", {"source_path": str(source_mirror), "path": "missing"})
    assert payload["ok"] is False
    assert "module not found" in payload["error"]


async def test_find_similar_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "find_similar", {"source_path": str(source_mirror), "path": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


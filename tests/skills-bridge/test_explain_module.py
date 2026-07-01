from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_explain_module_success(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "explain_module",
        {"source_path": str(source_mirror), "path": "CommonModules/Accounting/Ext/Module.bsl"},
    )
    assert payload["ok"] is True
    assert payload["symbols"][0]["name"] == "Recalculate"
    assert "Log" in payload["external_calls"]


async def test_explain_module_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "explain_module", {"source_path": str(source_mirror), "path": "missing"})
    assert payload["ok"] is False
    assert "module not found" in payload["error"]


async def test_explain_module_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "explain_module", {"source_path": str(source_mirror), "path": ""})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_query_optimizer_success(skills_client):
    payload = await call_tool_json(skills_client, "query_optimizer", {"query": "ВЫБРАТЬ * ИЗ Catalog.Товары"})
    assert payload["ok"] is True
    assert {item["code"] for item in payload["findings"]} >= {"SELECT_STAR", "NO_WHERE"}


async def test_query_optimizer_not_found(skills_client):
    payload = await call_tool_json(skills_client, "query_optimizer", {"query": "ВЫБРАТЬ Code ИЗ Catalog.Товары ГДЕ Code = &Code"})
    assert payload["ok"] is True
    assert payload["finding_count"] == 0


async def test_query_optimizer_invalid_input(skills_client):
    payload = await call_tool_json(skills_client, "query_optimizer", {"query": ""})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


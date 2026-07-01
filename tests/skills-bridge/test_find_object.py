from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_find_object_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "find_object", {"source_path": str(source_mirror), "name": "Products"})
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["matches"][0]["name"] == "Products"


async def test_find_object_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "find_object", {"source_path": str(source_mirror), "name": "Missing"})
    assert payload["ok"] is True
    assert payload["count"] == 0


async def test_find_object_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "find_object", {"source_path": str(source_mirror), "name": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


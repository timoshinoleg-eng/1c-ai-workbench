from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_meta_info_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "meta_info", {"source_path": str(source_mirror), "object_path": "Products"})
    assert payload["ok"] is True
    assert payload["metadata"]["name"] == "Products"
    assert payload["items"][0]["name"] == "Code"


async def test_meta_info_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "meta_info", {"source_path": str(source_mirror), "object_path": "Missing"})
    assert payload["ok"] is False
    assert "object not found" in payload["error"]


async def test_meta_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "meta_info", {"source_path": str(source_mirror), "object_path": "", "mode": "bad"})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_role_info_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "role_info", {"source_path": str(source_mirror), "role": "Manager"})
    assert payload["ok"] is True
    assert payload["role"]["name"] == "Manager"
    assert payload["rights"]


async def test_role_info_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "role_info", {"source_path": str(source_mirror), "role": "Missing"})
    assert payload["ok"] is False
    assert "role not found" in payload["error"]


async def test_role_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "role_info", {"source_path": str(source_mirror), "role": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


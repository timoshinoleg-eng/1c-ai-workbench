from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_subsystem_info_success(skills_client, source_mirror, stub_skill_subprocess):
    payload = await call_tool_json(skills_client, "subsystem_info", {"source_path": str(source_mirror), "subsystem_path": "Sales"})
    assert payload["ok"] is True
    assert payload["returncode"] == 0


async def test_subsystem_info_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "subsystem_info", {"source_path": str(source_mirror), "subsystem_path": "Missing"})
    assert payload["ok"] is False
    assert "target not found" in payload["error"]


async def test_subsystem_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "subsystem_info", {"source_path": str(source_mirror), "subsystem_path": "Sales", "mode": "bad"})
    assert payload["ok"] is False
    assert "String should match pattern" in str(payload["error"])


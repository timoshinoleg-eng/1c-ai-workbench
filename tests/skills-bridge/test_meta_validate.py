from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_meta_validate_success(skills_client, source_mirror, stub_skill_subprocess):
    payload = await call_tool_json(skills_client, "meta_validate", {"source_path": str(source_mirror), "object_path": "Products"})
    assert payload["ok"] is True
    assert payload["returncode"] == 0


async def test_meta_validate_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "meta_validate", {"source_path": str(source_mirror), "object_path": "Missing"})
    assert payload["ok"] is False
    assert "target not found" in payload["error"]


async def test_meta_validate_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "meta_validate", {"source_path": str(source_mirror), "object_path": "", "max_errors": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


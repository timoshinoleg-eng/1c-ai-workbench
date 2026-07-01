from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


SKD_PATH = "Reports/Sales/Ext"


async def test_skd_info_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "skd_info", {"source_path": str(source_mirror), "path": SKD_PATH})
    assert payload["ok"] is True
    assert payload["datasets"]
    assert payload["fields"]
    assert payload["parameters"]


async def test_skd_info_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "skd_info", {"source_path": str(source_mirror), "path": "missing"})
    assert payload["ok"] is False
    assert "SKD target not found" in payload["error"]


async def test_skd_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "skd_info", {"source_path": str(source_mirror), "path": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


FORM_PATH = "DataProcessors/Loader/Forms/Main/Ext/Form.xml"


async def test_form_info_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "form_info", {"source_path": str(source_mirror), "form_path": FORM_PATH})
    assert payload["ok"] is True
    assert payload["attributes"][0]["name"] == "Item"
    assert payload["commands"]


async def test_form_info_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "form_info", {"source_path": str(source_mirror), "form_path": "missing"})
    assert payload["ok"] is False
    assert "form not found" in payload["error"]


async def test_form_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "form_info", {"source_path": str(source_mirror), "form_path": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


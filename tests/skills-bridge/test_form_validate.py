from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


FORM_PATH = "DataProcessors/Loader/Forms/Main/Ext/Form.xml"


async def test_form_validate_success(skills_client, source_mirror, stub_skill_subprocess):
    payload = await call_tool_json(skills_client, "form_validate", {"source_path": str(source_mirror), "form_path": FORM_PATH})
    assert payload["ok"] is True
    assert payload["returncode"] == 0


async def test_form_validate_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "form_validate", {"source_path": str(source_mirror), "form_path": "missing"})
    assert payload["ok"] is False
    assert "target not found" in payload["error"]


async def test_form_validate_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "form_validate",
        {"source_path": str(source_mirror), "form_path": FORM_PATH, "max_errors": 0},
    )
    assert payload["ok"] is False
    assert "greater than or equal to 1" in str(payload["error"])


from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_cf_info_success(skills_client, source_mirror, stub_skill_subprocess):
    payload = await call_tool_json(skills_client, "cf_info", {"source_path": str(source_mirror), "mode": "brief"})
    assert payload["ok"] is True
    assert payload["returncode"] == 0
    assert "Configuration.xml" in payload["config_path"]


async def test_cf_info_not_found(skills_client, source_mirror):
    (source_mirror / "Configuration.xml").unlink()
    payload = await call_tool_json(skills_client, "cf_info", {"source_path": str(source_mirror)})
    assert payload["ok"] is False
    assert "Configuration.xml not found" in payload["error"]


async def test_cf_info_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "cf_info", {"source_path": str(source_mirror), "mode": "bad"})
    assert payload["ok"] is False
    assert "String should match pattern" in str(payload["error"])


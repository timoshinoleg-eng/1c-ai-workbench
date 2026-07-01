from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_cfe_diff_success(skills_client, source_mirror, stub_skill_subprocess):
    payload = await call_tool_json(
        skills_client,
        "cfe_diff",
        {"source_path": str(source_mirror), "extension_path": "extension", "config_path": "config"},
    )
    assert payload["ok"] is True
    assert payload["returncode"] == 0


async def test_cfe_diff_not_found(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "cfe_diff",
        {"source_path": str(source_mirror), "extension_path": "missing", "config_path": "config"},
    )
    assert payload["ok"] is False
    assert "extension path not found" in payload["error"]


async def test_cfe_diff_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "cfe_diff",
        {"source_path": str(source_mirror), "extension_path": "extension", "config_path": "config", "mode": "Z"},
    )
    assert payload["ok"] is False
    assert "String should match pattern" in str(payload["error"])


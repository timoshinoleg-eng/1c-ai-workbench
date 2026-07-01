from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_compare_versions_success(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "compare_versions",
        {"left_path": str(source_mirror / "left"), "right_path": str(source_mirror / "right")},
    )
    assert payload["ok"] is True
    assert payload["counts"]["changed"] == 1


async def test_compare_versions_not_found(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "compare_versions",
        {"left_path": str(source_mirror / "left"), "right_path": str(source_mirror / "missing")},
    )
    assert payload["ok"] is False
    assert "existing directories" in payload["error"]


async def test_compare_versions_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(
        skills_client,
        "compare_versions",
        {"left_path": str(source_mirror / "left"), "right_path": str(source_mirror / "right"), "limit": 0},
    )
    assert payload["ok"] is False
    assert "greater than or equal to 1" in str(payload["error"])


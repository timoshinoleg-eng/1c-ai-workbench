from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_audit_metadata_success(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "audit_metadata", {"source_path": str(source_mirror)})
    assert payload["ok"] is True
    assert payload["objects_scanned"] >= 3
    assert "finding_counts" in payload


async def test_audit_metadata_not_found(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "audit_metadata", {"source_path": str(source_mirror / "missing")})
    assert payload["ok"] is False
    assert "source-mirror root not found" in str(payload["error"])


async def test_audit_metadata_invalid_input(skills_client, source_mirror):
    payload = await call_tool_json(skills_client, "audit_metadata", {"source_path": str(source_mirror), "limit": 0})
    assert payload["ok"] is False
    assert "greater than or equal to 1" in str(payload["error"])


from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import call_tool_json


async def test_prompt_gallery_list_success(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_list", {})
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["prompts"][0]["slug"] == "review-bsl"


async def test_prompt_gallery_get_success(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(
        prompt_gallery_client,
        "prompt_gallery_get",
        {"name": "review-bsl", "task": "review module", "context": "Catalogs.Products", "language": "en"},
    )
    assert payload["ok"] is True
    assert payload["slug"] == "review-bsl"
    assert "MCP Caller Context" in payload["prompt"]
    assert "- Preferred language: en" in payload["prompt"]


async def test_prompt_gallery_get_not_found(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_get", {"name": "missing"})
    assert payload["ok"] is False
    assert "prompt not found" in payload["error"]


async def test_prompt_gallery_get_invalid_input(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_get", {"name": ""})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


async def test_prompt_gallery_search_success(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_search", {"query": "metadata", "limit": 5})
    assert payload["ok"] is True
    assert payload["matches"][0]["slug"] == "review-bsl"


async def test_prompt_gallery_search_not_found(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_search", {"query": "absent"})
    assert payload["ok"] is True
    assert payload["matches"] == []


async def test_prompt_gallery_search_invalid_input(prompt_gallery_client, prompt_gallery_fixture):
    payload = await call_tool_json(prompt_gallery_client, "prompt_gallery_search", {"query": "", "limit": 0})
    assert payload["ok"] is False
    assert "at least 1 character" in str(payload["error"])


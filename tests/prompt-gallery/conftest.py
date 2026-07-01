from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import pytest
import pytest_asyncio

warnings.filterwarnings(
    "ignore",
    message="SelectableGroups dict interface is deprecated.*",
    category=DeprecationWarning,
)

from fastmcp import Client


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_GALLERY_SERVER = REPO_ROOT / "tools" / "prompt-gallery" / "server.py"


@pytest.fixture(scope="session")
def prompt_gallery_server():
    spec = importlib.util.spec_from_file_location("prompt_gallery_server_under_test", PROMPT_GALLERY_SERVER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def prompt_gallery_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt_gallery_server) -> Path:
    workbench_root = tmp_path / "workbench"
    prompts_dir = workbench_root / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "review-bsl.md").write_text(
        """# /review-bsl - Review BSL

**Когда использовать:** нужно проверить BSL-модуль.

**Описание:** находит рискованные места в BSL-коде.

Body with query optimizer and metadata audit context.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(prompt_gallery_server, "WORKBENCH_ROOT", workbench_root)
    monkeypatch.setattr(prompt_gallery_server, "PROMPTS_DIR", prompts_dir)
    return prompts_dir


@pytest_asyncio.fixture
async def prompt_gallery_client(prompt_gallery_server):
    async with Client(prompt_gallery_server.mcp) as client:
        yield client


async def call_tool_json(client: Client, name: str, arguments: dict[str, object]) -> dict[str, object]:
    result = await client.call_tool(name, arguments)
    return json.loads(result.data)

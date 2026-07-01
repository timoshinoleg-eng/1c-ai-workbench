from __future__ import annotations

import importlib
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
SKILLS_BRIDGE_ROOT = REPO_ROOT / "tools" / "skills-bridge"


@pytest.fixture(scope="session")
def skills_server():
    sys.path.insert(0, str(SKILLS_BRIDGE_ROOT))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module("server")


@pytest_asyncio.fixture
async def skills_client(skills_server):
    async with Client(skills_server.mcp) as client:
        yield client


async def call_tool_json(client: Client, name: str, arguments: dict[str, object]) -> dict[str, object]:
    result = await client.call_tool(name, arguments)
    return json.loads(result.data)


@pytest.fixture
def source_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, skills_server) -> Path:
    workbench_root = tmp_path / "workbench"
    root = workbench_root / "source-mirror"
    root.mkdir(parents=True)

    (root / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject uuid="cfg-1">
  <Properties>
    <Name>DemoConfiguration</Name>
    <Synonym><item><content>Demo configuration</content></item></Synonym>
  </Properties>
  <Attribute>
    <Properties>
      <Name>MainCompany</Name>
      <Synonym><item><content>Main company</content></item></Synonym>
      <Type>CatalogRef.Organizations</Type>
    </Properties>
  </Attribute>
</MetaDataObject>
""",
        encoding="utf-8",
    )

    catalogs = root / "Catalogs"
    catalogs.mkdir()
    (catalogs / "Products.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject uuid="catalog-products">
  <Properties>
    <Name>Products</Name>
    <Synonym><item><content>Products</content></item></Synonym>
  </Properties>
  <Attribute>
    <Properties>
      <Name>Code</Name>
      <Synonym><item><content>Code</content></item></Synonym>
      <Type>String</Type>
    </Properties>
  </Attribute>
</MetaDataObject>
""",
        encoding="utf-8",
    )

    roles_ext = root / "Roles" / "Manager" / "Ext"
    roles_ext.mkdir(parents=True)
    (root / "Roles" / "Manager.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject uuid="role-manager">
  <Properties>
    <Name>Manager</Name>
    <Synonym><item><content>Manager</content></item></Synonym>
  </Properties>
</MetaDataObject>
""",
        encoding="utf-8",
    )
    (roles_ext / "Rights.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Rights><Right name="Read">true</Right><ObjectRight name="Catalogs.Products">Read</ObjectRight></Rights>
""",
        encoding="utf-8",
    )

    form_dir = root / "DataProcessors" / "Loader" / "Forms" / "Main" / "Ext"
    form_dir.mkdir(parents=True)
    (form_dir / "Form.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Form name="MainForm">
  <Attribute name="Item" id="1" />
  <Button name="RunCommand" id="2" />
  <CommandBar name="MainCommands" id="3" />
</Form>
""",
        encoding="utf-8",
    )

    report_ext = root / "Reports" / "Sales" / "Ext"
    report_ext.mkdir(parents=True)
    (report_ext / "Settings.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<DataCompositionSchema>
  <DataSet name="Main"><Field name="Amount" /><Parameter name="Period" /></DataSet>
  <Variant name="Default" />
</DataCompositionSchema>
""",
        encoding="utf-8",
    )
    template_ext = root / "Reports" / "Sales" / "Templates" / "Main" / "Ext"
    template_ext.mkdir(parents=True)
    (template_ext / "Template.xml").write_text("<Template><Area name=\"Header\" /></Template>", encoding="utf-8")

    subsystem_dir = root / "Subsystems"
    subsystem_dir.mkdir()
    (subsystem_dir / "Sales.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject uuid="subsystem-sales">
  <Properties><Name>Sales</Name><Synonym><item><content>Sales</content></item></Synonym></Properties>
</MetaDataObject>
""",
        encoding="utf-8",
    )

    module_a = root / "CommonModules" / "Accounting" / "Ext"
    module_b = root / "CommonModules" / "Sales" / "Ext"
    module_a.mkdir(parents=True)
    module_b.mkdir(parents=True)
    module_a.joinpath("Module.bsl").write_text(
        "Процедура Recalculate(Item) Экспорт\n    Log(Item);\nКонецПроцедуры\n",
        encoding="utf-8",
    )
    module_b.joinpath("Module.bsl").write_text(
        "Процедура RecalculateSale(Item) Экспорт\n    Log(Item);\nКонецПроцедуры\n",
        encoding="utf-8",
    )

    (root / "extension").mkdir()
    (root / "config").mkdir()
    (root / "left").mkdir()
    (root / "right").mkdir()
    (root / "left" / "same.txt").write_text("old", encoding="utf-8")
    (root / "right" / "same.txt").write_text("new", encoding="utf-8")

    common = importlib.import_module("tools.common")
    compare_versions = importlib.import_module("tools.compare_versions")
    monkeypatch.setattr(common, "WORKBENCH_ROOT", workbench_root)
    monkeypatch.setattr(common, "DEFAULT_SOURCE_PATHS", ())
    monkeypatch.setattr(compare_versions, "WORKBENCH_ROOT", workbench_root)
    return root


@pytest.fixture
def stub_skill_subprocess(monkeypatch: pytest.MonkeyPatch, skills_server):
    class CompletedProcess:
        returncode = 0
        stdout = "stubbed skill script output"
        stderr = ""

    def run(*args, **kwargs):
        return CompletedProcess()

    monkeypatch.setattr("subprocess.run", run)

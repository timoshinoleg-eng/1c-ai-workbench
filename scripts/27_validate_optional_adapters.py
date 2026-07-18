from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_ADAPTERS = {"mxl-merge-tool", "1c-odata-mcp", "feenlace-mcp-1c"}
FAIL_CLOSED_FIELDS: dict[str, Any] = {
    "enabled": False,
    "installer_bundled": False,
    "inherit_credentials": False,
    "allow_write_operations": False,
    "allowed_roots": [],
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Validate disabled-by-default external 1C adapters.")
    parser.add_argument("--config", type=Path, default=root / "configs/optional-adapters.json")
    args = parser.parse_args()

    payload = json.loads(args.config.resolve().read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise AssertionError("Unsupported optional adapter schema")
    for field, expected in FAIL_CLOSED_FIELDS.items():
        if payload.get("default_policy", {}).get(field) != expected:
            raise AssertionError(f"Default adapter policy must set {field}={expected!r}")

    adapters = payload.get("adapters", [])
    ids = [adapter.get("id") for adapter in adapters]
    if len(ids) != len(set(ids)):
        raise AssertionError("Optional adapter ids must be unique")
    if set(ids) != REQUIRED_ADAPTERS:
        raise AssertionError(f"Optional adapter set drifted: {set(ids)!r}")
    for adapter in adapters:
        for field, expected in FAIL_CLOSED_FIELDS.items():
            if adapter.get(field) != expected:
                raise AssertionError(f"{adapter['id']} must set {field}={expected!r}")
        for field in ("version", "source", "license", "activation_gate", "removal"):
            if not isinstance(adapter.get(field), str) or not adapter[field].strip():
                raise AssertionError(f"{adapter['id']} is missing {field}")

    rendered = json.dumps({"adapters": ids, "default_policy": "disabled", "verdict": "PASS"}, indent=2) + "\n"
    sys.stdout.buffer.write(rendered.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

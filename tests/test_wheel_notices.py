from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_python_wheel_notices.py"


def write_wheel(
    wheelhouse: Path,
    *,
    name: str,
    license_expression: str | None,
    license_text: str | None,
) -> None:
    wheel = wheelhouse / f"{name}-1.0-py3-none-any.whl"
    metadata = ["Metadata-Version: 2.4", f"Name: {name}", "Version: 1.0"]
    if license_expression:
        metadata.append(f"License-Expression: {license_expression}")
    dist_info = f"{name}-1.0.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"{dist_info}/METADATA", "\n".join(metadata) + "\n")
        if license_text:
            archive.writestr(f"{dist_info}/licenses/LICENSE", license_text)


def run_generator(wheelhouse: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(wheelhouse)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_generates_inventory_and_notices_from_exact_wheel(tmp_path: Path) -> None:
    write_wheel(
        tmp_path,
        name="example",
        license_expression="Apache-2.0",
        license_text="Apache License, Version 2.0",
    )

    result = run_generator(tmp_path)

    assert result.returncode == 0, result.stderr
    inventory = json.loads((tmp_path / "THIRD_PARTY_PYTHON.json").read_text("utf-8"))
    assert inventory["wheel_count"] == 1
    assert inventory["packages"][0]["detected_license"] == "Apache-2.0"
    assert len(inventory["packages"][0]["wheel_sha256"]) == 64
    notices = (tmp_path / "THIRD_PARTY_NOTICES.txt").read_text("utf-8")
    assert "example 1.0 (Apache-2.0)" in notices
    assert "Apache License, Version 2.0" in notices


def test_rejects_gpl_family_dependency(tmp_path: Path) -> None:
    write_wheel(
        tmp_path,
        name="copyleft",
        license_expression="GPL-3.0-only",
        license_text="GNU GENERAL PUBLIC LICENSE Version 3",
    )

    result = run_generator(tmp_path)

    assert result.returncode == 1
    assert "GPL-family license requires manual legal review" in result.stderr
    assert not (tmp_path / "THIRD_PARTY_PYTHON.json").exists()

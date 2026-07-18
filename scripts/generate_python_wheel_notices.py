from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

LICENSE_FILE_PATTERN = re.compile(
    r"(?:^|/)(?:licenses?/)?(?:licen[cs]e|copying|notice)(?:[._-].*)?$",
    re.IGNORECASE,
)
DENIED_PATTERN = re.compile(
    r"\b(?:AGPL|GPL|LGPL)(?:[- v]?\d(?:\.\d)?)?\b|" r"GNU (?:AFFERO |LESSER )?GENERAL PUBLIC LICENSE",
    re.IGNORECASE,
)
KNOWN_LICENSES = (
    (re.compile(r"Apache License(?:,? Version)? 2\.0|Apache-2\.0", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"MIT License|\bMIT\b", re.IGNORECASE), "MIT"),
    (re.compile(r"BSD 3-Clause|BSD-3-Clause", re.IGNORECASE), "BSD-3-Clause"),
    (re.compile(r"BSD 2-Clause|BSD-2-Clause", re.IGNORECASE), "BSD-2-Clause"),
    (re.compile(r"BSD License|License :: OSI Approved :: BSD License|^BSD$", re.IGNORECASE), "BSD-3-Clause"),
    (re.compile(r"Python Software Foundation|PSF-2\.0", re.IGNORECASE), "PSF-2.0"),
    (re.compile(r"Mozilla Public License(?:,? Version)? 2\.0|MPL-2\.0", re.IGNORECASE), "MPL-2.0"),
    (re.compile(r"ISC License|\bISC\b", re.IGNORECASE), "ISC"),
    (re.compile(r"The Unlicense|\bUnlicense\b", re.IGNORECASE), "Unlicense"),
    (re.compile(r"CC0(?:-1\.0)?|Creative Commons Zero", re.IGNORECASE), "CC0-1.0"),
    (re.compile(r"Blue Oak Model License", re.IGNORECASE), "BlueOak-1.0.0"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory licenses embedded in a Python wheelhouse.")
    parser.add_argument("wheelhouse", type=Path)
    return parser.parse_args()


def decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AssertionError("latin-1 decoding must always succeed")


def detect_license(evidence: str) -> str | None:
    for pattern, identifier in KNOWN_LICENSES:
        if pattern.search(evidence):
            return identifier
    return None


def wheel_record(wheel: Path) -> tuple[dict[str, object], list[tuple[str, str]]]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError(f"{wheel.name}: expected one dist-info/METADATA, got {len(metadata_names)}")
        message = BytesParser(policy=default).parsebytes(archive.read(metadata_names[0]))
        license_entries = sorted(name for name in names if ".dist-info/" in name and LICENSE_FILE_PATTERN.search(name))
        license_texts = [
            (name, decode_text(archive.read(name)).replace("\r\n", "\n").strip())
            for name in license_entries
            if not name.endswith("/")
        ]

    metadata_evidence = "\n".join(
        filter(
            None,
            [
                message.get("License-Expression", ""),
                message.get("License", ""),
                *message.get_all("Classifier", []),
            ],
        )
    )
    license_file_evidence = "\n".join(text for _, text in license_texts)
    detected = detect_license(metadata_evidence)
    if detected is None and DENIED_PATTERN.search(metadata_evidence):
        raise ValueError(f"{wheel.name}: GPL-family license requires manual legal review")
    if detected is None:
        detected = detect_license(license_file_evidence)
        if detected is None and DENIED_PATTERN.search(license_file_evidence):
            raise ValueError(f"{wheel.name}: GPL-family license requires manual legal review")
    if detected is None:
        raise ValueError(f"{wheel.name}: no supported license evidence found")

    record: dict[str, object] = {
        "name": message.get("Name"),
        "version": message.get("Version"),
        "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "detected_license": detected,
        "license_expression": message.get("License-Expression"),
        "license_metadata": message.get("License"),
        "project_urls": message.get_all("Project-URL", []),
        "license_files": [name for name, _ in license_texts],
    }
    if not record["name"] or not record["version"]:
        raise ValueError(f"{wheel.name}: Name or Version is missing from METADATA")
    return record, license_texts


def main() -> int:
    args = parse_args()
    wheelhouse = args.wheelhouse.resolve()
    wheels = sorted(wheelhouse.glob("*.whl"), key=lambda item: item.name.lower())
    if not wheels:
        raise ValueError(f"No wheels found in {wheelhouse}")

    records: list[dict[str, object]] = []
    notice_sections: list[str] = []
    errors: list[str] = []
    for wheel in wheels:
        try:
            record, license_texts = wheel_record(wheel)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(str(exc))
            continue
        records.append(record)
        heading = f"{record['name']} {record['version']} ({record['detected_license']})"
        contents = [f"Declared license: {record['detected_license']}"]
        contents.extend(f"--- {filename} ---\n{license_text}" for filename, license_text in license_texts)
        notice_sections.append(f"{'=' * len(heading)}\n{heading}\n{'=' * len(heading)}\n\n" + "\n\n".join(contents))

    if errors:
        for error in errors:
            print(f"[LICENSE ERROR] {error}", file=sys.stderr)
        return 1

    inventory = {
        "schema_version": 1,
        "policy": "License evidence present; GPL-family dependencies denied pending manual legal review.",
        "wheel_count": len(records),
        "packages": records,
    }
    (wheelhouse / "THIRD_PARTY_PYTHON.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    notice_header = (
        "Third-party Python packages bundled with 1C AI Workbench\n"
        "Generated from the exact wheel files in this offline installer.\n\n"
    )
    (wheelhouse / "THIRD_PARTY_NOTICES.txt").write_text(
        notice_header + "\n\n".join(notice_sections) + "\n", encoding="utf-8"
    )
    print(f"[OK] Verified license evidence for {len(records)} wheels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

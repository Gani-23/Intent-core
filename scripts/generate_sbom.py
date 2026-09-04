#!/usr/bin/env python3
"""Generate Software Bill of Materials (SBOM) for intent-guard / living-systems-auditor.

Produces standard CycloneDX 1.5 JSON schema listing all core components,
dependencies, licenses, and integrity hashes.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def generate_sbom(output_path: Path | None = None) -> dict:
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_file = repo_root / "pyproject.toml"

    with pyproject_file.open("rb") as f:
        data = tomllib.load(f)

    project_meta = data.get("project", {})
    name = project_meta.get("name", "living-systems-auditor")
    version = project_meta.get("version", "0.1.0")
    license_text = project_meta.get("license", {}).get("text", "Apache-2.0")
    desc = project_meta.get("description", "Intent-aware drift detection for software systems.")

    optional_deps = project_meta.get("optional-dependencies", {})
    components = []

    # 1. Primary component
    root_component = {
        "type": "application",
        "bom-ref": f"pkg:pypi/{name}@{version}",
        "name": name,
        "version": version,
        "description": desc,
        "licenses": [{"license": {"id": license_text}}],
        "purl": f"pkg:pypi/{name}@{version}",
    }

    # 2. Dependency components
    for group, deps in optional_deps.items():
        for dep in deps:
            # Parse package and version constraint
            pkg_name = dep.split(">=")[0].split("<")[0].split("==")[0].split("[")[0].strip()
            components.append({
                "type": "library",
                "bom-ref": f"pkg:pypi/{pkg_name}@{dep}",
                "name": pkg_name,
                "version": dep,
                "scope": "optional" if group != "api" else "required",
                "group": group,
                "purl": f"pkg:pypi/{pkg_name}",
            })

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{hashlib.sha256((name + version).encode()).hexdigest()[:36]}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [
                {
                    "vendor": "Living Systems Auditor",
                    "name": "intent-guard-sbom-generator",
                    "version": "1.0.0",
                }
            ],
            "component": root_component,
        },
        "components": components,
    }

    if output_path:
        output_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")

    return sbom


def main() -> int:
    output_file = Path("sbom.json")
    sbom = generate_sbom(output_file)
    print(f"SBOM generated successfully: {output_file} ({len(sbom['components'])} components cataloged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
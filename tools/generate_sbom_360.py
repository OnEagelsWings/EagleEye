from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component(requirement: str, scope: str) -> dict:
    raw = requirement.strip()
    name = re.split(r"[<>=!~\[; ]", raw, maxsplit=1)[0].strip()
    exact = re.search(r"==\s*([^,; ]+)", raw)
    item = {
        "type": "library",
        "name": name,
        "bom-ref": f"pkg:pypi/{name.lower().replace('_','-')}",
        "purl": f"pkg:pypi/{name.lower().replace('_','-')}",
        "properties": [
            {"name": "eagleeye:declared_requirement", "value": raw},
            {"name": "eagleeye:dependency_scope", "value": scope},
        ],
    }
    if exact:
        item["version"] = exact.group(1)
        item["purl"] += "@" + exact.group(1)
        item["bom-ref"] = item["purl"]
    return item


def generate(root: Path) -> dict:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    meta = project["project"]
    components = []
    for req in meta.get("dependencies", []):
        components.append(_component(req, "runtime"))
    for group, reqs in sorted(meta.get("optional-dependencies", {}).items()):
        for req in reqs:
            components.append(_component(req, f"optional:{group}"))
    components.sort(key=lambda x: (x["name"].lower(), x["properties"][1]["value"]))
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:36000000-0000-4000-8000-000000000360",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": meta["name"], "version": meta["version"]},
            "properties": [
                {"name": "eagleeye:sbom_scope", "value": "declared-direct-and-optional-dependencies"},
                {"name": "eagleeye:requirements-runtime-sha256", "value": _sha(root / "requirements-runtime.txt")},
                {"name": "eagleeye:requirements-windows-sha256", "value": _sha(root / "requirements-windows.txt")},
                {"name": "eagleeye:transitive_lock_status", "value": "not_claimed"}
            ],
        },
        "components": components,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output", type=Path)
    ns = ap.parse_args()
    out = ns.output or ns.root / "SBOM_BUILD_360_0.cdx.json"
    payload = generate(ns.root)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "components": len(payload["components"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path

from resurrectum.spec.schemas import SCHEMA_NAMES, SchemaRegistry, load_json

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "docs" / "examples"


def test_examples_validate_against_schemas() -> None:
    registry = SchemaRegistry.default()

    assert EXAMPLES_ROOT.is_dir()

    validated = 0
    for path in sorted(EXAMPLES_ROOT.rglob("*.json")):
        schema_name = SCHEMA_NAMES.get(path.name)
        if not schema_name:
            continue
        payload = load_json(path)
        registry.validate_instance(payload, schema_name)
        validated += 1

    assert validated > 0

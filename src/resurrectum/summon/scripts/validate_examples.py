from __future__ import annotations

import sys
from pathlib import Path

from resurrectum.spec.schemas import SCHEMA_NAMES, SchemaRegistry, SchemaValidationError, load_json


def main() -> int:
    registry = SchemaRegistry.default()
    examples_root = registry.schema_root.parent.parent / "examples"

    if not examples_root.is_dir():
        print(f"Examples directory not found: {examples_root}")
        return 1

    failures: list[str] = []
    validated = 0

    for path in sorted(examples_root.rglob("*.json")):
        schema_name = SCHEMA_NAMES.get(path.name)
        if not schema_name:
            continue
        payload = load_json(path)
        try:
            registry.validate_instance(payload, schema_name)
        except SchemaValidationError as exc:
            failures.append(f"{path}: {exc}")
            failures.extend(f"  - {err}" for err in exc.errors)
        else:
            validated += 1

    if failures:
        print("Schema validation failures:")
        for line in failures:
            print(line)
        return 1

    print(f"Validated {validated} example file(s) successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

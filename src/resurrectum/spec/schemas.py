from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import FormatChecker

SCHEMA_NAMES = {
    "capsule.manifest.json": "capsule.manifest.schema.json",
    "redaction.report.json": "redaction.report.schema.json",
    "restore.report.json": "restore.report.schema.json",
}


class SchemaValidationError(ValueError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


@dataclass(frozen=True)
class SchemaRegistry:
    schema_root: Path

    @staticmethod
    def discover_root(start: Path | None = None) -> Path:
        if start is None:
            start = Path(__file__).resolve()
        for candidate in [start, *start.parents]:
            docs_root = candidate / "docs" / "schemas" / "v1"
            if docs_root.is_dir():
                return docs_root
        raise FileNotFoundError("Unable to locate Resurrectum schemas/v1 directory.")

    @classmethod
    def default(cls) -> "SchemaRegistry":
        return cls(schema_root=cls.discover_root())

    def schema_path(self, schema_filename: str) -> Path:
        return self.schema_root / schema_filename

    def load_schema(self, schema_filename: str) -> dict[str, Any]:
        path = self.schema_path(schema_filename)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def validator_for(self, schema_filename: str) -> jsonschema.Validator:
        schema = self.load_schema(schema_filename)
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        return validator_cls(schema, format_checker=FormatChecker())

    def validate_instance(self, instance: dict[str, Any], schema_filename: str) -> None:
        validator = self.validator_for(schema_filename)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        if errors:
            formatted = [self._format_error(err) for err in errors]
            raise SchemaValidationError(
                f"Schema validation failed for {schema_filename}.",
                errors=formatted,
            )

    @staticmethod
    def _format_error(error: jsonschema.ValidationError) -> str:
        location = "/".join(str(part) for part in error.path) or "<root>"
        return f"{location}: {error.message}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

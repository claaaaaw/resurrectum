from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schemas import SchemaRegistry, SchemaValidationError, load_json, write_json


@dataclass(frozen=True)
class CapsuleManifest:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any], registry: SchemaRegistry | None = None) -> "CapsuleManifest":
        registry = registry or SchemaRegistry.default()
        registry.validate_instance(payload, "capsule.manifest.schema.json")
        return cls(payload)

    @classmethod
    def from_path(cls, path: Path, registry: SchemaRegistry | None = None) -> "CapsuleManifest":
        payload = load_json(path)
        return cls.from_dict(payload, registry=registry)

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def write(self, path: Path) -> None:
        write_json(path, self.data)


@dataclass(frozen=True)
class RedactionReport:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any], registry: SchemaRegistry | None = None) -> "RedactionReport":
        registry = registry or SchemaRegistry.default()
        registry.validate_instance(payload, "redaction.report.schema.json")
        return cls(payload)

    @classmethod
    def from_path(cls, path: Path, registry: SchemaRegistry | None = None) -> "RedactionReport":
        payload = load_json(path)
        return cls.from_dict(payload, registry=registry)

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def write(self, path: Path) -> None:
        write_json(path, self.data)


@dataclass(frozen=True)
class RestoreReport:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any], registry: SchemaRegistry | None = None) -> "RestoreReport":
        registry = registry or SchemaRegistry.default()
        registry.validate_instance(payload, "restore.report.schema.json")
        return cls(payload)

    @classmethod
    def from_path(cls, path: Path, registry: SchemaRegistry | None = None) -> "RestoreReport":
        payload = load_json(path)
        return cls.from_dict(payload, registry=registry)

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def write(self, path: Path) -> None:
        write_json(path, self.data)


__all__ = [
    "CapsuleManifest",
    "RedactionReport",
    "RestoreReport",
    "SchemaValidationError",
]

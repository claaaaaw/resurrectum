# Memory Capsule — Migration & Compatibility (OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** Compatibility and migration rules for OpenClaw-only Memory Capsule v1 and v1.x evolution.

## 0. Goals
- Maintain compatibility across OpenClaw workspace evolution.
- Support backward/forward compatibility across capsule spec versions.

## Related docs
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`
- Roadmap: `10-ROADMAP.md`

## 1. Compatibility rules (v1)
- Capsule tooling MUST NOT require changes to OpenClaw file formats.
- Unknown files under `memory/` are treated as opaque artifacts (allowlist rules still apply).
- New OpenClaw files introduced later MUST be excluded by default until explicitly added to allowlist/policy.

## 2. Capsule versioning strategy
- `spec_version`: `v1`, `v1.1`, ...
- `capsule_id`: UUIDv7 (stable identifier for one exported snapshot)
- v1.x: backward-compatible additions only.
- v2: breaking changes.

Importer behavior:
- If `spec_version` is newer than supported:
  - `validate` fails with a clear message
  - `import` fails by default
  - optionally `--best-effort` can attempt restoring known fields only (future)

## 3. Workspace migration
- Import should restore files into a target workspace without overwriting by default.
- Provide `restore.report.json` that lists:
  - created files
  - skipped files (already exist)
  - conflicts

## 4. Policy migration
- Redaction policy version must be recorded in `redaction.report.json`.
- If policy changes, re-export is required to apply new boundaries.

## 5. Future (reserved)
- Lineage: `parents[]` and DAG merges.
- Differential exports.
- Vector index encapsulation.

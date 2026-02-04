# Memory Capsule — Conformance Tests v1 (OpenClaw-only)

**Audience:** AI engineers

**v1 scope:** Normative conformance test requirements for OpenClaw-only Memory Capsule v1.

## 0. Goal
Define the compatibility bar so any implementation can be verified as:

## Related docs
- Requirements: `01-PRD.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- OpenClaw-compatible
- AI-first (Machine Layer contract correct)
- Secure-by-default

## 1. Test fixture conventions
Fixtures live in `conformance/fixtures/`:
- `workspace_minimal/` (sample OpenClaw workspace)
- `workspace_with_secrets/` (contains forbidden files + secret strings)
- `expected_capsule_minimal/` (golden manifest/report)

## 2. Required tests (v1)
### 2.1 Round-trip (byte-identical)
**Given** a fixture workspace
- Run `export` to capsule
- Delete workspace
- Run `import` into empty workspace

**Assert**
- Restored files match byte-for-byte for allowlisted artifacts
- `capsule.manifest.json` is valid
- `redaction.report.json` exists and is valid

### 2.2 Policy strict mode (fail closed)
Fixture contains:
- `.env`
- `memory/moltbook.json`
- `*_cookies.json`

**Assert**
- `export --strict` exits with code `2`
- redaction report lists decisions as `exclude` for forbidden items
- report contains findings types only (no secret substrings)

### 2.3 Dry run (normative v1)
**Assert**
- `openclaw capsule export --dry-run` produces only `redaction.report.json`
- no blobs are written
- no manifest is written

### 2.4 Tamper detection
After export:
- modify one stored blob

**Assert**
- `validate` fails with code `5`

### 2.5 Signature + canonicalization required
After export:
- remove `signature` field OR mutate any signed field in manifest

**Assert**
- `validate` fails with code `4`

Additionally (bytes-to-sign test):
- validator recomputes bytes-to-sign using **RFC 8785 JCS** of manifest without `signature` (UTF-8, no trailing newline).
- signatures MUST verify only against those bytes (not ad-hoc JSON serialization).

### 2.6 Wrong passphrase
**Assert**
- `import` fails with code `6`
- no partial workspace written unless `--partial`

### 2.7 Trusted signer pinning
Validate/import with a signer that is not trusted.

**Assert**
- `validate` fails with code `4` (signature/trust failure)
- `import` fails before any decrypt/restore

## 3. Definition: “OpenClaw-compatible” (v1)
An implementation is compatible if:
- It can export/import OpenClaw workspace files listed in PRD without changing their formats.
- It treats `memory/` as extensible and does not hardcode filenames.
- It applies strict redaction defaults and never exports secrets in plaintext.

## 4. Next step
- Provide golden examples for `capsule.manifest.json` and `redaction.report.json`.
- Add a CI job that runs these tests on every change.

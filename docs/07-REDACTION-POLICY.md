# Memory Capsule — Redaction Policy v1 (OpenClaw-only, strict)

**Audience:** AI engineers

**v1 scope:** Normative redaction boundary and default policy for OpenClaw-only Memory Capsule v1.

## 0. Purpose
Define how Memory Capsule decides what to include/exclude/redact when exporting an OpenClaw workspace.

## Related docs
- Requirements: `01-PRD.md`
- Architecture: `02-ARCHITECTURE.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- Threat model: `06-SECURITY-THREAT-MODEL.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`

This is a **hard v1 requirement**.

## 1. Principles
- **Fail closed by default.**
- **OpenClaw-first allowlist.** Only known-safe workspace paths are included by default.
- **Never leak secrets in reports.** Findings must not contain raw values or matching substrings.
- **Deterministic decisions.** Same inputs + same policy → same decisions.

## 2. Data classification (v1)
- **Public:** safe plaintext (rare)
- **Private:** export OK, but encrypted
- **Sensitive:** export only with explicit opt-in (still encrypted)
- **Forbidden:** never export in v1 unless explicit override (`--i-know-what-im-doing`)

## 3. Default allowlist (OpenClaw-only)
Included by default (subject to content scanning):
- `MEMORY.md`
- `memory/**` (md/json), **except** denylist below
- `SOUL.md`, `USER.md`, `IDENTITY.md`
- `AGENTS.md`, `TOOLS.md`, `HEARTBEAT.md`
- `projects/**/STATUS.md`

Everything else is excluded unless explicitly allowed.

## 4. Default denylist (Forbidden by default)
Always excluded unless override:
- `.env`
- `**/*.pem`, `**/*id_rsa*`, `**/*private_key*`
- `**/*token*`, `**/*secret*`
- `**/*cookies*.json`, `**/*_cookies.json`
- `memory/moltbook.json` (credentials)
- browser profiles / session stores / sqlite cookie jars
- files above size threshold (configurable)

## 5. Detectors (heuristic)
Detectors run on candidate files (streaming when possible):
- API key patterns (`sk-`, `ghp_`, etc.)
- JWT patterns
- private key block markers
- cookie/session field markers

Detector output:
- `rule_id`
- `severity`
- `locations` (line numbers / byte offsets)

**Never include matched strings.**

## 6. Decisions & actions
Per artifact, policy chooses one:
- `exclude`
- `include_encrypted` (default for allowed files)
- `include_redacted` (rewrite content; store only redacted bytes)
- `include_plaintext` (discouraged; requires explicit allow)

v1 default behavior:
- Any Forbidden match → `exclude` and (in strict mode) block export.
- Sensitive match → `exclude` unless explicit opt-in.

## 7. Reports (machine-readable)
Export MUST emit `redaction.report.json` with:
- policy version
- detectors run + config hash
- per-file decisions + reasons
- findings summary

Safety rule:
- findings include **types/rule IDs/locations only**.

## 8. CLI guardrails
- `--dry-run`: produce only redaction report
- `--strict` (default): any Forbidden finding blocks export
- `--i-know-what-im-doing`: required to include Forbidden class

## 9. Open questions (future)
- Optional path encryption to reduce metadata leakage
- Configurable PII detectors (names, addresses) with false-positive controls

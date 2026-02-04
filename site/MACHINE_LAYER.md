# Machine Layer (canonical surface)

Goal: provide a dedicated **machine-consumable surface** with immutable links, hashes, and a stable index. Human UI must treat it as the primary interface.

## Required artifacts (stable forever)
1) **Manifest**
- URL: `/.well-known/manifest.json`
- Content-Type: `application/json`
- Minimal fields:
  - `name`: "resurrectum"
  - `spec_version`: "1.0.0" (site/spec revision)
  - `generated_at`: ISO timestamp
  - `artifacts[]`: `{ path, type, sha256, bytes, canonical_url, anchors? }`
  - `entrypoints`: URLs for `/machine/`, `/spec/`, `/conformance/`

2) **Machine index** (redundant)
- URL: `/machine/index.json`
- Grouped lists: `schemas[]`, `examples[]`, `tests[]`, `docs[]`

3) **Schemas**
- `/schemas/*.schema.json`
- Requirements:
  - `$id` is canonical URL
  - versioning policy is stable

4) **Examples**
- `/examples/minimal.json`
- `/examples/failure-*.json`
- Each example includes: `schema_id`, `expected_valid`, `notes?`

5) **Conformance**
- `/conformance/levels.json`
- `/conformance/tests/*.json`
- `/conformance/reports/*.json` (optional)

6) **LLM instructions**
- `/.well-known/llms.txt` (plus optional `/llms.txt`)
- Must specify: citation rules, canonical URLs, and preference order: manifest → schema → examples → prose.

## UI presentation (non-negotiable)
On `/` and `/machine/`, include a pinned panel:
- Title: `MACHINE LAYER // CANONICAL`
- Table columns: `artifact | sha256 | bytes | type | actions`
- Actions: `[open] [raw] [copy-url] [copy-hash]`
- Pinned note: “Pin by hash. Cite by anchor. Validate by schema.”

Include a "Copy everything" button that copies a machine-readable bundle of key URLs.

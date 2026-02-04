# IA / Sitemap (URLs + stable anchors)

Principle: **Every human-facing section has a corresponding machine-stable anchor**, and every machine artifact is linked from a single “Machine Layer” block that never moves.

## Core routes

### `/` (Index / Entrance)
- `#prelude` — doctrine (cold, declarative)
- `#quickstart` — **single-line command** (placeholder allowed)
- `#axioms` — axioms/vows
- `#machine-layer` — canonical machine block
- `#proofs` — verifiable claims (hashes/refs)
- `#rituals` — “how to invoke / integrate” (static)
- `#threat-model` — what it is / is not
- `#changelog` — releases/spec revisions
- `#contact` — optional (framed as “Witness channel”)

### `/spec/` (Human-readable spec front page)
- `#scope`
- `#terms`
- `#protocol`
- `#schemas`
- `#anchors` — stable anchor index
- `#conformance` — vectors + compliance levels

### `/spec/contract/` (Primary contract)
- `#contract-header`
- `#definitions`
- `#normative`
- `#non-normative`
- `#security`

### `/spec/anchors/` (Anchor registry)
- `#anchor-table`
- `#deprecation`

### `/machine/` (Machine Layer landing)
- `#artifacts`
- `#schemas`
- `#examples`
- `#conformance`
- `#llm-instructions`

### `/examples/`
- `#minimal`
- `#flows`
- `#failure-modes`

### `/conformance/`
- `#levels` — e.g. Witness / Adept / Canon
- `#tests`
- `#reports`

### `/changelog/`
- `#releases`
- `#breaking`

## Artifact routes (public API; must remain stable)
- `/.well-known/manifest.json` (or `/manifest.json`)
- `/.well-known/llms.txt` (and/or `/llms.txt`)
- `/machine/index.json`
- `/schemas/*.schema.json`
- `/examples/*.json`
- `/conformance/*.json`
- `/spec/*.md` (optional raw sources)

# Stack Recommendation (static, spec-first)

## Recommendation
**Astro + Starlight**
- Naturally “spec/doc” feeling
- Fast static output, simple hosting
- Easy to keep `/spec/` as MD/MDX while shipping `/machine/` JSON artifacts

If you want even more austere: Astro without Starlight + custom layout.

## Proposed file tree
```text
/
├─ public/
│  ├─ .well-known/
│  │  ├─ manifest.json
│  │  └─ llms.txt
│  ├─ machine/
│  │  └─ index.json
│  ├─ schemas/
│  │  ├─ contract.schema.json
│  │  ├─ invocation.schema.json
│  │  └─ conformance.schema.json
│  ├─ examples/
│  │  ├─ minimal.json
│  │  ├─ flow-basic.json
│  │  └─ failure-invalid-anchor.json
│  └─ conformance/
│     ├─ levels.json
│     ├─ tests/
│     └─ reports/
├─ src/
│  ├─ content/docs/
│  │  ├─ index.mdx
│  │  ├─ contract.mdx
│  │  ├─ anchors.mdx
│  │  ├─ protocol.mdx
│  │  └─ changelog.mdx
│  ├─ pages/
│  │  ├─ index.astro
│  │  ├─ machine.astro
│  │  ├─ examples.astro
│  │  └─ conformance.astro
│  ├─ components/
│  │  ├─ MachineLayerPanel.astro
│  │  ├─ AnchorGutter.astro
│  │  └─ NormativeBlock.astro
│  └─ styles/
│     ├─ theme.css
│     └─ tokens.css
└─ package.json
```

## Implementation notes
- Explicit heading IDs in MDX (no auto slugs drifting)
- Anchor registry page (`/spec/anchors/`) is part of the public API
- A build step can compute sha256 and generate manifest/index deterministically

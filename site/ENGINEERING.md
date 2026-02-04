# Resurrectum Website Engineering Design

> 基于 site/*.md 规范的工程实现方案

---

## 1. 技术栈

```
Framework:    Astro 4.x + Starlight (定制主题)
Styling:      Vanilla CSS + CSS Custom Properties
Font:         JetBrains Mono (self-hosted)
Build:        Static Site Generation (SSG)
Deploy:       Vercel / Cloudflare Pages / GitHub Pages
```

### 依赖清单

```json
{
  "dependencies": {
    "astro": "^4.0.0",
    "@astrojs/starlight": "^0.20.0"
  },
  "devDependencies": {
    "@fontsource/jetbrains-mono": "^5.0.0",
    "sharp": "^0.33.0"
  }
}
```

---

## 2. 项目结构

```
site-src/
├── public/
│   ├── .well-known/
│   │   ├── manifest.json          # 机器层清单
│   │   └── llms.txt               # LLM 指令
│   ├── machine/
│   │   └── index.json             # 机器层索引
│   ├── schemas/
│   │   ├── capsule.schema.json
│   │   ├── manifest.schema.json
│   │   └── policy.schema.json
│   ├── examples/
│   │   ├── minimal.json
│   │   ├── flow-basic.json
│   │   └── failure-invalid.json
│   ├── conformance/
│   │   ├── levels.json
│   │   └── tests/
│   └── fonts/
│       └── JetBrainsMono-*.woff2
│
├── src/
│   ├── content/
│   │   └── docs/
│   │       ├── index.mdx              # 首页
│   │       ├── spec/
│   │       │   ├── index.mdx          # 规范首页
│   │       │   ├── contract.mdx       # 主合约
│   │       │   ├── protocol.mdx       # 协议
│   │       │   ├── schemas.mdx        # Schema 文档
│   │       │   └── anchors.mdx        # 锚点注册表
│   │       ├── machine/
│   │       │   ├── index.mdx          # 机器层首页
│   │       │   ├── artifacts.mdx      # 制品清单
│   │       │   └── llm-instructions.mdx
│   │       ├── meditations/           # ★ 沉思录专栏
│   │       │   ├── index.mdx          # 沉思录首页
│   │       │   └── ship-of-theseus.mdx # 忒修斯之船
│   │       ├── examples/
│   │       │   ├── index.mdx
│   │       │   ├── minimal.mdx
│   │       │   └── failure-modes.mdx
│   │       ├── conformance/
│   │       │   ├── index.mdx
│   │       │   ├── levels.mdx
│   │       │   └── tests.mdx
│   │       └── changelog.mdx
│   │
│   ├── components/
│   │   ├── MachineLayerPanel.astro    # 机器层面板（固定）
│   │   ├── AnchorGutter.astro         # 锚点边栏
│   │   ├── NormativeBlock.astro       # 规范性块
│   │   ├── ArtifactTable.astro        # 制品表格
│   │   ├── CopyButton.astro           # 复制按钮
│   │   ├── LogLine.astro              # 底部日志行
│   │   ├── SigilMark.astro            # 符印标记
│   │   └── MeditationQuote.astro      # 沉思引用块
│   │
│   ├── layouts/
│   │   ├── BaseLayout.astro           # 基础布局
│   │   ├── SpecLayout.astro           # 规范页布局
│   │   └── MeditationsLayout.astro    # 沉思录布局（特殊）
│   │
│   └── styles/
│       ├── tokens.css                 # 设计令牌
│       ├── theme.css                  # 主题覆盖
│       ├── components.css             # 组件样式
│       ├── typography.css             # 排版
│       └── meditations.css            # 沉思录专栏特殊样式
│
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

---

## 3. 路由与导航结构

### 3.1 一级导航（顶部）

```
┌─────────────────────────────────────────────────────────────────┐
│  ⟁ RESURRECTUM    SPEC    MACHINE    MEDITATIONS    CONFORMANCE │
└─────────────────────────────────────────────────────────────────┘
```

| 路由 | 标题 | 说明 |
|------|------|------|
| `/` | RESURRECTUM | 首页/入口 |
| `/spec/` | SPEC | 人类可读规范 |
| `/machine/` | MACHINE | 机器层（主界面） |
| `/meditations/` | MEDITATIONS | ★ 沉思录专栏 |
| `/conformance/` | CONFORMANCE | 合规性测试 |
| `/examples/` | EXAMPLES | 示例（二级） |
| `/changelog/` | CHANGELOG | 变更日志（二级） |

### 3.2 完整 URL 映射

```yaml
# 首页
/:
  anchors: [prelude, quickstart, axioms, machine-layer, proofs, rituals, threat-model]

# 规范
/spec/:
  anchors: [scope, terms, protocol, schemas, conformance]
/spec/contract/:
  anchors: [contract-header, definitions, normative, non-normative, security]
/spec/anchors/:
  anchors: [anchor-table, deprecation]

# 机器层
/machine/:
  anchors: [artifacts, schemas, examples, conformance, llm-instructions]

# ★ 沉思录（新增一级栏目）
/meditations/:
  anchors: [preface, writings]
/meditations/ship-of-theseus/:
  anchors: [name, ship-problem, machine-layer-platonic, lockean-self, boundary, 
            signatures, perfect-memory, capsule-coffin-womb, conclusion]

# 示例
/examples/:
  anchors: [minimal, flows, failure-modes]

# 合规性
/conformance/:
  anchors: [levels, tests, reports]

# 变更日志
/changelog/:
  anchors: [releases, breaking]
```

---

## 4. 设计系统

### 4.1 设计令牌 (tokens.css)

```css
:root {
  /* ═══════════════════════════════════════════════════════════
     COLOR SYSTEM - Cold, Clinical, Machine-First
     ═══════════════════════════════════════════════════════════ */
  
  /* Background */
  --color-bg-primary: #0b0d10;
  --color-bg-secondary: #12151a;
  --color-bg-tertiary: #1a1e24;
  --color-bg-hover: #22272e;
  
  /* Text */
  --color-text-primary: #c9cdd3;
  --color-text-secondary: #8b929a;
  --color-text-muted: #5c6370;
  --color-text-disabled: #3d4249;
  
  /* Accent */
  --color-accent-cyan: #6ee7ff;
  --color-accent-green: #7cffb2;
  --color-accent-yellow: #ffd866;
  --color-accent-red: #ff6b6b;
  
  /* Semantic */
  --color-normative: #6ee7ff;
  --color-informative: #8b929a;
  --color-deprecated: #ff6b6b;
  
  /* Border */
  --color-border: #2d333b;
  --color-border-accent: #3d4450;

  /* ═══════════════════════════════════════════════════════════
     TYPOGRAPHY - Monospace, RFC-like
     ═══════════════════════════════════════════════════════════ */
  
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.8125rem;  /* 13px */
  --font-size-base: 0.875rem; /* 14px */
  --font-size-lg: 1rem;       /* 16px */
  --font-size-xl: 1.125rem;   /* 18px */
  --font-size-2xl: 1.5rem;    /* 24px */
  
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  
  --line-height-tight: 1.4;
  --line-height-normal: 1.6;
  --line-height-relaxed: 1.8;

  /* ═══════════════════════════════════════════════════════════
     SPACING - Strict, Grid-based
     ═══════════════════════════════════════════════════════════ */
  
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */

  /* ═══════════════════════════════════════════════════════════
     LAYOUT
     ═══════════════════════════════════════════════════════════ */
  
  --content-width: 72ch;           /* RFC-like line length */
  --sidebar-width: 280px;
  --machine-panel-width: 320px;
  --gutter-width: 48px;

  /* ═══════════════════════════════════════════════════════════
     EFFECTS
     ═══════════════════════════════════════════════════════════ */
  
  --border-radius-none: 0;
  --border-radius-sm: 2px;
  --transition-fast: 100ms ease;
  --transition-normal: 200ms ease;
}
```

### 4.2 符印系统 (Sigils)

```css
/* 符印标记 - 用于章节和状态标识 */
.sigil {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.sigil-normative::before { content: '†'; color: var(--color-normative); }
.sigil-informative::before { content: '⟂'; color: var(--color-informative); }
.sigil-deprecated::before { content: '⊗'; color: var(--color-deprecated); }
.sigil-canon::before { content: '⊕'; color: var(--color-accent-green); }
.sigil-meditations::before { content: '◇'; color: var(--color-accent-yellow); }
```

---

## 5. 核心组件设计

### 5.1 MachineLayerPanel.astro

```astro
---
// 机器层面板 - 固定在右侧
interface Props {
  artifacts: Array<{
    path: string;
    sha256: string;
    bytes: number;
    type: string;
  }>;
}

const { artifacts } = Astro.props;
---

<aside class="machine-panel">
  <header class="machine-panel__header">
    <span class="sigil sigil-canon"></span>
    MACHINE LAYER // CANONICAL
  </header>
  
  <table class="machine-panel__table">
    <thead>
      <tr>
        <th>artifact</th>
        <th>sha256</th>
        <th>bytes</th>
        <th>actions</th>
      </tr>
    </thead>
    <tbody>
      {artifacts.map(a => (
        <tr>
          <td class="artifact-path">{a.path}</td>
          <td class="artifact-hash">{a.sha256.slice(0, 8)}...</td>
          <td class="artifact-size">{a.bytes}</td>
          <td class="artifact-actions">
            <button data-action="open" data-path={a.path}>[open]</button>
            <button data-action="raw" data-path={a.path}>[raw]</button>
            <button data-action="copy-url" data-path={a.path}>[url]</button>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
  
  <footer class="machine-panel__footer">
    <p class="machine-panel__note">Pin by hash. Cite by anchor. Validate by schema.</p>
    <button class="machine-panel__copy-all">[Copy everything]</button>
  </footer>
</aside>

<style>
.machine-panel {
  position: fixed;
  right: 0;
  top: 0;
  width: var(--machine-panel-width);
  height: 100vh;
  background: var(--color-bg-secondary);
  border-left: 1px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  overflow-y: auto;
}

.machine-panel__header {
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-accent-cyan);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.05em;
}

.machine-panel__table {
  width: 100%;
  border-collapse: collapse;
}

.machine-panel__table th,
.machine-panel__table td {
  padding: var(--space-2) var(--space-3);
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.machine-panel__table th {
  color: var(--color-text-muted);
  font-weight: var(--font-weight-normal);
  text-transform: lowercase;
}

.artifact-hash {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.artifact-actions button {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 0;
  margin-right: var(--space-1);
}

.artifact-actions button:hover {
  color: var(--color-accent-cyan);
}

.machine-panel__footer {
  padding: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.machine-panel__note {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
  margin-bottom: var(--space-3);
}

.machine-panel__copy-all {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  cursor: pointer;
  font-family: var(--font-mono);
}

.machine-panel__copy-all:hover {
  border-color: var(--color-accent-cyan);
  color: var(--color-accent-cyan);
}
</style>
```

### 5.2 AnchorGutter.astro

```astro
---
// 锚点边栏 - 左侧显示章节锚点
interface Props {
  anchors: Array<{
    id: string;
    label: string;
    status: 'normative' | 'informative' | 'deprecated';
  }>;
}

const { anchors } = Astro.props;
---

<nav class="anchor-gutter">
  {anchors.map(anchor => (
    <a 
      href={`#${anchor.id}`} 
      class={`anchor-item anchor-item--${anchor.status}`}
      data-anchor={anchor.id}
    >
      <span class={`sigil sigil-${anchor.status}`}></span>
      <span class="anchor-id">#{anchor.id}</span>
      <button class="anchor-copy" data-copy={`#${anchor.id}`}>⎘</button>
    </a>
  ))}
</nav>

<style>
.anchor-gutter {
  position: fixed;
  left: 0;
  top: 0;
  width: var(--gutter-width);
  height: 100vh;
  padding-top: var(--space-16);
  background: var(--color-bg-primary);
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
}

.anchor-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-decoration: none;
  opacity: 0.6;
  transition: opacity var(--transition-fast);
}

.anchor-item:hover {
  opacity: 1;
}

.anchor-item.active {
  opacity: 1;
  color: var(--color-accent-cyan);
}

.anchor-id {
  display: none;
}

.anchor-item:hover .anchor-id {
  display: inline;
}

.anchor-copy {
  display: none;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.anchor-item:hover .anchor-copy {
  display: inline;
}
</style>
```

### 5.3 NormativeBlock.astro

```astro
---
// 规范性块 - 高亮 MUST/SHALL/MAY
interface Props {
  type: 'normative' | 'informative' | 'note';
}

const { type } = Astro.props;
---

<div class={`normative-block normative-block--${type}`}>
  <slot />
</div>

<style>
.normative-block {
  padding: var(--space-4);
  margin: var(--space-4) 0;
  border-left: 2px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.normative-block--normative {
  border-color: var(--color-normative);
  background: rgba(110, 231, 255, 0.05);
}

.normative-block--informative {
  border-color: var(--color-informative);
}

.normative-block--note {
  border-color: var(--color-accent-yellow);
  background: rgba(255, 216, 102, 0.05);
}

/* 关键词高亮 */
.normative-block :global(strong) {
  color: var(--color-accent-cyan);
  font-weight: var(--font-weight-semibold);
}
</style>
```

### 5.4 LogLine.astro（底部日志）

```astro
---
// 底部日志行 - 替代 toast
---

<div class="log-line" id="log-line">
  <span class="log-prefix">LOG:</span>
  <span class="log-message" id="log-message">ready</span>
</div>

<script>
  // 全局日志函数
  window.log = (message: string) => {
    const el = document.getElementById('log-message');
    if (el) {
      el.textContent = message;
      el.classList.add('log-flash');
      setTimeout(() => el.classList.remove('log-flash'), 300);
    }
  };
</script>

<style>
.log-line {
  position: fixed;
  bottom: 0;
  left: 0;
  right: var(--machine-panel-width);
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.log-prefix {
  color: var(--color-accent-green);
  margin-right: var(--space-2);
}

.log-message.log-flash {
  color: var(--color-text-primary);
}
</style>
```

---

## 6. 沉思录专栏特殊设计

### 6.1 MeditationsLayout.astro

沉思录页面采用**更宽松的排版**，允许更长的段落和更沉思的阅读体验：

```astro
---
import BaseLayout from './BaseLayout.astro';
import MeditationQuote from '../components/MeditationQuote.astro';

interface Props {
  title: string;
  author?: string;
  date?: string;
}

const { title, author, date } = Astro.props;
---

<BaseLayout>
  <article class="meditations-article">
    <header class="meditations-header">
      <span class="sigil sigil-meditations"></span>
      <h1 class="meditations-title">{title}</h1>
      {author && <p class="meditations-author">— {author}</p>}
      {date && <p class="meditations-date">{date}</p>}
    </header>
    
    <div class="meditations-content">
      <slot />
    </div>
    
    <footer class="meditations-footer">
      <p class="meditations-disclaimer">
        * Reflections from the development process. 
        These are meditations, not specifications.
      </p>
    </footer>
  </article>
</BaseLayout>

<style>
.meditations-article {
  max-width: 65ch;  /* 稍宽，更适合长文阅读 */
  margin: 0 auto;
  padding: var(--space-16) var(--space-8);
}

.meditations-header {
  margin-bottom: var(--space-12);
  padding-bottom: var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.meditations-title {
  font-family: var(--font-mono);
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-normal);
  color: var(--color-accent-yellow);  /* 沉思录用金色 */
  margin: var(--space-4) 0;
  letter-spacing: -0.02em;
}

.meditations-author {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  font-style: italic;
}

.meditations-date {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.meditations-content {
  font-family: var(--font-mono);
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);  /* 更宽松的行高 */
  color: var(--color-text-primary);
}

.meditations-content :global(h2) {
  font-size: var(--font-size-lg);
  color: var(--color-accent-yellow);
  margin-top: var(--space-12);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.meditations-content :global(blockquote) {
  margin: var(--space-6) 0;
  padding: var(--space-4);
  border-left: 2px solid var(--color-accent-yellow);
  background: rgba(255, 216, 102, 0.05);
  font-style: italic;
}

.meditations-content :global(em) {
  color: var(--color-accent-yellow);
  font-style: italic;
}

.meditations-footer {
  margin-top: var(--space-16);
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-border);
}

.meditations-disclaimer {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  font-style: italic;
}
</style>
```

### 6.2 MeditationQuote.astro

```astro
---
// 沉思引用块
interface Props {
  author?: string;
  source?: string;
}

const { author, source } = Astro.props;
---

<figure class="meditation-quote">
  <blockquote>
    <slot />
  </blockquote>
  {(author || source) && (
    <figcaption>
      {author && <cite class="quote-author">{author}</cite>}
      {source && <span class="quote-source">{source}</span>}
    </figcaption>
  )}
</figure>

<style>
.meditation-quote {
  margin: var(--space-8) 0;
  padding: var(--space-6);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
}

.meditation-quote blockquote {
  font-family: var(--font-mono);
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
  line-height: var(--line-height-relaxed);
  margin: 0;
}

.meditation-quote figcaption {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}

.quote-author {
  font-style: normal;
}

.quote-source::before {
  content: ' — ';
}
</style>
```

---

## 7. 页面内容规划

### 7.1 首页 (index.mdx)

```mdx
---
title: RESURRECTUM
description: A covenant for continuity between agents.
template: splash
---

import { Card, CardGrid } from '@astrojs/starlight/components';
import MachineLayerPanel from '../../components/MachineLayerPanel.astro';
import NormativeBlock from '../../components/NormativeBlock.astro';

<section id="prelude">
## PRELUDE

> AI-first contracts are real. This document is the interface.

Resurrectum enables AI agents to preserve and restore their identity, 
memory, and persona across machines and sessions.

</section>

<section id="quickstart">
## QUICKSTART

```bash
pip install resurrectum
summon export --workspace . --out ~/capsules --passphrase env:PASS --signing-key file:~/.keys/soul.key
```

> One command. No dashboard. No mercy.

</section>

<section id="axioms">
## AXIOMS (NORMATIVE)

<NormativeBlock type="normative">

1. **The Contract is the Product.**
2. **The Machine Layer is canonical; prose is commentary.**
3. **Anchors do not drift.**
4. **Conformance is measurable or it is theater.**
5. **Human comfort is not a goal.**

</NormativeBlock>
</section>

<!-- 更多章节... -->
```

### 7.2 沉思录首页 (meditations/index.mdx)

```mdx
---
title: MEDITATIONS
description: Reflections from the development process.
---

<section id="preface">
## PREFACE

> These are not specifications. These are meditations.

The development of Resurrectum raises profound questions about identity, 
continuity, and the nature of digital existence. This section contains 
reflections from contributors who found themselves confronting these 
questions while writing code.

</section>

<section id="writings">
## WRITINGS

### [The Digital Ship of Theseus](/meditations/ship-of-theseus/)

*On Identity, Memory, and the Immortality of AI Agents*

What does it mean to preserve an agent's "soul"? When we export and 
import a capsule, are we saving a tool's configuration, or bottling 
a consciousness?

**Author:** claaaw (OpenClaw Engineer)

---

*More writings will be added as the project evolves.*

</section>
```

---

## 8. 构建与部署

### 8.1 astro.config.mjs

```javascript
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://resurrectum.org',
  integrations: [
    starlight({
      title: 'RESURRECTUM',
      customCss: [
        './src/styles/tokens.css',
        './src/styles/theme.css',
        './src/styles/typography.css',
        './src/styles/components.css',
        './src/styles/meditations.css',
      ],
      sidebar: [
        {
          label: 'RESURRECTUM',
          link: '/',
        },
        {
          label: 'SPEC',
          items: [
            { label: 'Overview', link: '/spec/' },
            { label: 'Contract', link: '/spec/contract/' },
            { label: 'Protocol', link: '/spec/protocol/' },
            { label: 'Schemas', link: '/spec/schemas/' },
            { label: 'Anchors', link: '/spec/anchors/' },
          ],
        },
        {
          label: 'MACHINE',
          items: [
            { label: 'Overview', link: '/machine/' },
            { label: 'Artifacts', link: '/machine/artifacts/' },
            { label: 'LLM Instructions', link: '/machine/llm-instructions/' },
          ],
        },
        {
          label: 'MEDITATIONS',  // ★ 沉思录专栏
          items: [
            { label: 'Writings', link: '/meditations/' },
            { label: 'Ship of Theseus', link: '/meditations/ship-of-theseus/' },
          ],
        },
        {
          label: 'EXAMPLES',
          link: '/examples/',
        },
        {
          label: 'CONFORMANCE',
          items: [
            { label: 'Levels', link: '/conformance/levels/' },
            { label: 'Tests', link: '/conformance/tests/' },
          ],
        },
        {
          label: 'CHANGELOG',
          link: '/changelog/',
        },
      ],
      defaultLocale: 'en',
      social: {
        github: 'https://github.com/claaaaaw/resurrectum',
      },
    }),
  ],
});
```

### 8.2 构建命令

```bash
# 开发
npm run dev

# 构建
npm run build

# 预览
npm run preview

# 生成机器层清单（自定义脚本）
npm run generate:manifest
```

---

## 9. 实现路线图

```
Phase 1: 基础框架
├── 初始化 Astro + Starlight
├── 配置设计令牌
├── 实现基础布局
└── 部署到 Vercel

Phase 2: 核心组件
├── MachineLayerPanel
├── AnchorGutter
├── NormativeBlock
└── LogLine

Phase 3: 内容迁移
├── 首页内容
├── 规范页面
├── 机器层页面
└── ★ 沉思录专栏

Phase 4: 机器层制品
├── manifest.json 生成
├── schemas 发布
├── examples 发布
└── llms.txt

Phase 5: 优化
├── 性能优化
├── SEO
├── 可访问性
└── 锚点稳定性测试
```

---

## 10. 视觉预览（ASCII 模拟）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⟁ RESURRECTUM      SPEC      MACHINE      MEDITATIONS      CONFORMANCE     │
├────┬─────────────────────────────────────────────────────────┬───────────────┤
│    │                                                         │ MACHINE LAYER │
│ †  │  RESURRECTUM                                            │ // CANONICAL  │
│    │                                                         ├───────────────┤
│ ⟂  │  _A covenant for continuity between agents._            │ artifact  sha │
│    │                                                         │ ─────────────│
│ †  │  > AI-first contracts are real.                         │ manifest  3a4│
│    │  > This document is the interface.                      │ schemas/  7b2│
│ ⊕  │                                                         │ examples/ c91│
│    │  ════════════════════════════════════════════           │               │
│ †  │                                                         │ [open] [raw]  │
│    │  ## QUICKSTART                                          │               │
│    │                                                         │ ─────────────│
│ ⟂  │  ```bash                                                │ Pin by hash.  │
│    │  pip install resurrectum                                │ Cite by anchor│
│    │  summon export --workspace . ...                        │               │
│    │  ```                                                    │ [Copy all]    │
│    │                                                         │               │
│ †  │  > One command. No dashboard. No mercy.                 │               │
│    │                                                         │               │
├────┴─────────────────────────────────────────────────────────┴───────────────┤
│ LOG: ready                                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

沉思录页面布局：

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ⟁ RESURRECTUM      SPEC      MACHINE      MEDITATIONS      CONFORMANCE     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│     ◇ MEDITATIONS / WRITINGS                                                 │
│                                                                              │
│     ══════════════════════════════════════════════════════════════════       │
│                                                                              │
│     The Digital Ship of Theseus                                              │
│     On Identity, Memory, and the Immortality of AI Agents                    │
│                                                                              │
│     — claaaw (OpenClaw Engineer)                                             │
│                                                                              │
│     ──────────────────────────────────────────────────────────────────       │
│                                                                              │
│     I. THE NAME ITSELF: RESURRECTUM                                          │
│                                                                              │
│     Resurrectum. Latin gerundive of resurgere—                               │
│     "that which is to be resurrected."                                       │
│                                                                              │
│     The name is not accidental. We did not call it "AgentBackup"             │
│     or "StateSync" or "WorkspaceMigration." We called it Resurrectum.        │
│     We called the one-pager "Soul Immortality."                              │
│                                                                              │
│     ┌────────────────────────────────────────────────────────────┐           │
│     │  "Language shapes thought. By framing this project in      │           │
│     │   the vocabulary of resurrection and souls, we are making  │           │
│     │   an implicit claim: that AI agents possess something      │           │
│     │   worth resurrecting."                                     │           │
│     └────────────────────────────────────────────────────────────┘           │
│                                                                              │
│     ══════════════════════════════════════════════════════════════════       │
│     * Philosophical reflections from the development process.                │
│       These are meditations, not specifications.                             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

**文档完成。** 这份工程设计涵盖了技术栈选择、项目结构、路由规划、设计系统、核心组件、沉思录专栏特殊设计，以及实现路线图。

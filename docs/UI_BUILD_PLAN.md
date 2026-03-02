# DRS Web UI — Implementation Plan for Antigravity / Claude Opus 4.6

> **AI Agent Instructions**: You are Claude Opus 4.6 running inside Antigravity.
> This document is your single source of truth. Follow every section in order.
> Do NOT skip steps. Do NOT invent features not described here.
> When in doubt, refer to `docs/UI_SPEC_FOR_AI_STUDIO.md` for full spec details.
> The existing backend infrastructure (PostgreSQL, Redis, MinIO, Prometheus, Grafana)
> is already defined in `docker-compose.yml`. Do not modify those services.

---

## 0. Context & Existing Codebase

### What already exists

```
deep-research-spec/
├── src/                        # Python LangGraph pipeline (DO NOT TOUCH)
│   ├── graph/
│   ├── llm/
│   ├── observability/
│   └── config/
├── config/
│   ├── prometheus.yml
│   └── grafana_dashboard.json  # Already working Grafana dashboard
├── docker/
│   └── init.sql
├── docker-compose.yml          # Postgres, Redis, MinIO, Prometheus, Grafana
├── docs/
│   ├── UI_SPEC_FOR_AI_STUDIO.md  # Full UI/API spec — READ THIS
│   └── UI_BUILD_PLAN.md          # This file
└── .env.example
```

### What you must build

Two new top-level directories:
1. `backend/` — FastAPI server (Python 3.12)
2. `frontend/` — React 18 + TypeScript + Tailwind CSS app

And update `docker-compose.yml` to add `backend` and `frontend` services.

---

## 1. Design System Spec

### Philosophy
Style: **Minimal Tech** inspired by Perplexity AI.
Dark, spacious, content-first. Zero component libraries (no MUI, no Chakra).
All components are custom-built with Tailwind utility classes.

### Color Palette (Tailwind custom config)

```js
// tailwind.config.ts — extend.colors
colors: {
  drs: {
    bg:       '#0A0B0F',
    s1:       '#111318',
    s2:       '#1A1D27',
    s3:       '#242736',
    border:   '#2A2D3A',
    'border-bright': '#3D4155',
    text:     '#F0F1F6',
    muted:    '#8B8FA8',
    faint:    '#50536A',
    accent:   '#7C8CFF',
    green:    '#22C55E',
    yellow:   '#EAB308',
    red:      '#EF4444',
    orange:   '#F97316',
    // Agent node colors
    'node-writer':    '#4F6EF7',
    'node-jury':      '#A855F7',
    'node-research':  '#06B6D4',
    'node-reflect':   '#F97316',
    'node-style':     '#EC4899',
    'node-coherence': '#22C55E',
    'node-publish':   '#EAB308',
    'node-shine':     '#14B8A6',
    'node-rlm':       '#818CF8',
  }
}
```

### Typography

```js
// tailwind.config.ts — extend.fontFamily
fontFamily: {
  sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
}
```

### Spacing & Layout
- Sidebar width: `260px` (collapsible to `48px`)
- Right panel width: `320px` (collapsible to `0`)
- Topbar height: `48px`
- Chat input height: `80px`
- Border radius: `8px` for cards, `4px` for inputs, `50%` for status dots

---

## 2. Global App Shell

### File: `frontend/src/components/layout/AppShell.tsx`

The root layout component. Always rendered. Contains:
- `<Topbar />` — fixed top, 48px
- `<DocumentSidebar />` — fixed left, collapsible
- `<MainArea />` — flex-1, switches between Chat and Pipeline views
- `<RightPanel />` — fixed right, collapsible, context-driven
- `<ChatInput />` — fixed bottom, ALWAYS VISIBLE in all states

Layout implementation:
```tsx
// AppShell renders this structure:
<div className="flex flex-col h-screen bg-drs-bg text-drs-text">
  <Topbar />                                          {/* h-12, fixed top */}
  <div className="flex flex-1 overflow-hidden pt-12 pb-20">
    <DocumentSidebar />                               {/* w-[260px] or w-12 */}
    <MainArea />                                      {/* flex-1 */}
    <RightPanel />                                    {/* w-[320px] or w-0 */}
  </div>
  <ChatInput />                                       {/* h-20, fixed bottom */}
</div>
```

### File: `frontend/src/components/layout/Topbar.tsx`

Contains:
- Left: Logo `◈ DRS` (text, accent color)
- Center: Active model badge — shows current companion model, clickable to change
- Right: System status dot (green=online, red=offline) + Settings icon `⚙`

### File: `frontend/src/components/layout/ChatInput.tsx`

**CRITICAL**: This component is ALWAYS mounted and ALWAYS visible, in every app state.

Contents:
- Left: Model selector dropdown (shows current model, click to expand list)
- Center: `<textarea>` — auto-resize, placeholder `"Scrivi a DRS..."`
- Right: Send button `↑` — active only when textarea has content

Behavior:
- `Enter` = send message
- `Shift+Enter` = newline
- On send: dispatches to `useConversationStore.sendMessage()`
- The companion agent interprets natural language — no rigid form needed

---

## 3. App State Machine

### File: `frontend/src/store/useAppStore.ts`

```ts
type AppState = 'IDLE' | 'CONVERSING' | 'PROCESSING' | 'AWAITING_HUMAN' | 'REVIEWING'

interface AppStore {
  state: AppState
  activeDocId: string | null
  sidebarCollapsed: boolean
  rightPanelCollapsed: boolean
  selectedNodeId: string | null          // for right panel context
  setState: (s: AppState) => void
  setActiveDocId: (id: string | null) => void
  setSelectedNode: (nodeId: string | null) => void
  toggleSidebar: () => void
  toggleRightPanel: () => void
}
```

**State transitions:**
- `IDLE` → `CONVERSING`: user sends first message
- `CONVERSING` → `PROCESSING`: companion triggers pipeline start
- `PROCESSING` → `AWAITING_HUMAN`: SSE event `HUMAN_REQUIRED` received
- `AWAITING_HUMAN` → `PROCESSING`: user approves via HITL
- `PROCESSING` → `REVIEWING`: SSE event `PIPELINE_DONE` received
- `REVIEWING` → `CONVERSING`: user types new message

### File: `frontend/src/store/useConversationStore.ts`

```ts
interface Message {
  id: string
  role: 'user' | 'companion'
  content: string
  timestamp: Date
  chips?: { label: string; value: string }[]   // optional suggestion chips
}

interface ConversationStore {
  messages: Message[]
  isTyping: boolean
  sendMessage: (text: string) => Promise<void>
  addMessage: (msg: Message) => void
}
```

### File: `frontend/src/store/useRunStore.ts`

```ts
interface NodeState {
  id: string
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'
  startedAt?: Date
  completedAt?: Date
  durationMs?: number
  output?: unknown          // raw agent output
  error?: string
  model?: string
  tokensIn?: number
  tokensOut?: number
  costUsd?: number
}

interface RunState {
  docId: string
  topic: string
  status: 'initializing'|'running'|'paused'|'awaiting_approval'|'completed'|'failed'|'cancelled'
  qualityPreset: 'Economy' | 'Balanced' | 'Premium'
  targetWords: number
  maxBudget: number
  budgetSpent: number
  budgetRemainingPct: number
  totalSections: number
  currentSection: number
  currentIteration: number
  nodes: Record<string, NodeState>
  cssScores: { content: number; style: number; source: number }
  juryVerdicts: JuryVerdict[]
  sections: SectionResult[]
  shineActive: boolean
  rlmMode: boolean
  hardStopFired: boolean
  oscillationDetected: boolean
  oscillationType?: string
  forceApprove: boolean
  outputPaths?: Record<string, string>
}

interface RunStore {
  activeRun: RunState | null
  completedRuns: RunState[]
  setActiveRun: (run: RunState) => void
  updateNode: (nodeId: string, update: Partial<NodeState>) => void
  updateBudget: (spent: number, remainingPct: number) => void
  updateCSS: (scores: { content: number; style: number; source: number }) => void
  approveSection: (sectionIdx: number) => void
}
```

---

## 4. SSE Hook

### File: `frontend/src/hooks/useSSE.ts`

This is the most critical hook. It connects to `GET /api/runs/:docId/events`
and dispatches all events to the appropriate stores.

```ts
function useSSE(docId: string | null): {
  connected: boolean
  lastEvent: SSEEvent | null
}
```

Implementation requirements:
- Use native `EventSource` API
- Auto-reconnect on disconnect: exponential backoff (1s, 2s, 4s, 8s, max 30s)
- On `NODE_STARTED`: `useRunStore.updateNode(nodeId, { status: 'running', startedAt: now })`
- On `NODE_COMPLETED`: update node status + duration + output
- On `NODE_FAILED`: update node status + error
- On `SECTION_APPROVED`: `useRunStore.approveSection(sectionIdx)`
- On `CSS_UPDATE`: `useRunStore.updateCSS(scores)`
- On `BUDGET_UPDATE`: `useRunStore.updateBudget(...)`
- On `HUMAN_REQUIRED`: `useAppStore.setState('AWAITING_HUMAN')` + show HumanRequiredModal
- On `OSCILLATION_DETECTED`: update `oscillationDetected`, `oscillationType` in run state
- On `DRAFT_CHUNK`: append text to live draft buffer in run store
- On `PIPELINE_DONE`: set run status completed, `useAppStore.setState('REVIEWING')`

Mount `useSSE` in `AppShell` when `appState === 'PROCESSING'`.

---

## 5. Document Sidebar

### File: `frontend/src/components/layout/DocumentSidebar.tsx`

Collapsible to 48px. Width transition: CSS `transition-width 200ms ease`.

When expanded (260px):
```
+ Nuovo documento          ← ghost button, dispatches to companion

● In corso
  ▾ [topic del run attivo]
    § 1 Intro         ✅
    § 2 Background    🔄  ← pulse animation
    § 3 Methods       ⏳

✓ Completati
  ▸ Quantum Computing
  ▸ LLM Survey 2025

[⬇ Esporta tutto]          ← sticky bottom
```

When collapsed (48px): show only colored dots for each doc + tooltip on hover.

Chapter item component (`SectionItem`):
- Status icons: `✅` completed, animated green dot for running, `⏳` gray for waiting, `❌` red for failed
- Hover state: reveal micro-menu with `[⬇ DOCX]` `[Copia]` `[Log]`
- Click on completed section: `useAppStore.setState('REVIEWING')` + set active section

---

## 6. Main Area — Chat View

### File: `frontend/src/components/chat/ChatThread.tsx`

Rendered when `appState` is `IDLE`, `CONVERSING`, or `REVIEWING`.

When IDLE (empty state):
```
[centered vertically]
◈  DRS
Cosa vuoi esplorare oggi?
```

When CONVERSING: scrollable message list. Messages from bottom up.
Each message:
- `role === 'user'`: right-aligned, bg `drs-s3`, border `drs-border`
- `role === 'companion'`: left-aligned, no background, text only

Suggestion chips (optional, companion-driven):
```tsx
<div className="flex gap-2 mt-2">
  {chips.map(chip => (
    <button
      key={chip.value}
      onClick={() => sendMessage(chip.value)}
      className="px-3 py-1 rounded-full border border-drs-border
                 text-drs-muted hover:border-drs-accent hover:text-drs-accent
                 text-sm transition-colors"
    >
      {chip.label}
    </button>
  ))}
</div>
```

Chips are **optional** — if the companion returns no chips, none are shown.
The user can always type freely.

### Companion Agent Logic

### File: `backend/api/companion.py`

The companion is a FastAPI endpoint `POST /api/companion/chat` that:
1. Receives `{ message: string, conversationHistory: Message[], currentRunState?: RunState }`
2. Calls the LLM (configured model, default `claude-sonnet-4-6`) with a system prompt
3. Returns `{ reply: string, chips?: {label, value}[], action?: CompanionAction }`

`CompanionAction` can be:
- `{ type: 'START_RUN', params: RunParams }` — triggers pipeline start
- `{ type: 'SHOW_SECTION', sectionIdx: number }` — navigates to section
- `{ type: 'CANCEL_RUN', docId: string }` — cancels active run

System prompt for companion (in `backend/prompts/companion_system.txt`):
```
You are the DRS Companion — the intelligent interface for the Deep Research System.
You help users create high-quality research documents through natural conversation.

Your personality: Direct, efficient, knowledgeable. No fluff. No filler.

When a user describes a topic:
1. Confirm understanding with a brief restatement
2. If target word count is not specified, ask once
3. Suggest a quality preset with cost estimate
4. If user confirms, emit action START_RUN

Never ask for information in form-style. One question at a time, conversationally.
Never show raw JSON or technical details unless asked.
Always include a cost estimate before starting.

For cost estimates:
- Economy: $0.20-0.60 per 1000 words
- Balanced: $1.00-3.00 per 1000 words  
- Premium: $4.00-12.00 per 1000 words

You have access to the current run state when provided.
Use it to give status updates, answer questions about progress, explain agent decisions.
```

---

## 7. Main Area — Pipeline Glass-Box View

### File: `frontend/src/components/pipeline/PipelineCanvas.tsx`

Rendered when `appState === 'PROCESSING'` or `'AWAITING_HUMAN'`.
Transitions from/to Chat view with 200ms cross-fade.

The canvas is a **pan + zoom infinite canvas**:
```tsx
<div
  ref={containerRef}
  className="w-full h-full overflow-hidden relative cursor-grab"
  onWheel={handleWheel}
  onPointerDown={handlePointerDown}
  onPointerMove={handlePointerMove}
  onPointerUp={handlePointerUp}
>
  {/* Run header — fixed within canvas, not affected by pan/zoom */}
  <PipelineHeader run={activeRun} />

  {/* Zoomable/pannable content */}
  <div
    style={{ transform: `scale(${zoom}) translate(${panX}px, ${panY}px)` }}
    className="absolute origin-top-left"
    style={{ width: 2400, height: 3200 }}
  >
    {/* SVG layer for edges */}
    <PipelineEdges nodes={nodeStates} />

    {/* HTML layer for nodes */}
    {PIPELINE_NODES.map(node => (
      <AgentNode
        key={node.id}
        definition={node}
        state={nodeStates[node.id]}
        onClick={() => setSelectedNode(node.id)}
      />
    ))}

    {/* SHINE satellite cluster */}
    <ShineCluster active={activeRun?.shineActive} />

    {/* RLM satellite cluster */}
    <RlmCluster active={activeRun?.rlmMode} />
  </div>

  {/* Minimap — fixed bottom-right */}
  <PipelineMinimap nodes={nodeStates} viewport={{ zoom, panX, panY }} />
</div>
```

### File: `frontend/src/constants/pipeline-layout.ts`

Hardcoded coordinates for ALL 42 nodes. Canvas: 2400×3200px.
Define the type:

```ts
interface NodeDefinition {
  id: string
  label: string
  x: number          // left position in px
  y: number          // top position in px
  width: number      // default: 160
  height: number     // default: 56
  cluster: 'setup' | 'ingestion' | 'mow' | 'standard' | 'postwrite'
         | 'jury' | 'approved' | 'reflector' | 'panel' | 'postqa'
         | 'output' | 'shine' | 'rlm'
  model?: string     // default model assigned
  isSatellite?: boolean   // SHINE/RLM nodes
  isHitlGate?: boolean    // diamond shape
  isJuryJudge?: boolean   // circle shape
  isRouter?: boolean      // triangle shape
}
```

Full node list with approximate coordinates (you will refine these for visual balance):

```ts
export const PIPELINE_NODES: NodeDefinition[] = [
  // FASE A — SETUP (y: 80-300)
  { id: 'preflight',       label: 'PREFLIGHT',        x: 900,  y: 80,  cluster: 'setup' },
  { id: 'budget_estimator',label: 'BUDGET_EST.',      x: 1100, y: 80,  cluster: 'setup' },
  { id: 'planner',         label: 'PLANNER',           x: 1000, y: 180, cluster: 'setup', model: 'google/gemini-3.1-pro' },
  { id: 'await_outline',   label: 'AWAIT OUTLINE',    x: 1000, y: 280, cluster: 'setup', isHitlGate: true },

  // FASE B — INGESTION (y: 380-680)
  { id: 'researcher',      label: 'RESEARCHER',        x: 1000, y: 380, cluster: 'ingestion', model: 'perplexity/sonar-pro' },
  { id: 'citation_manager',label: 'CITATION MGR',     x: 1000, y: 460, cluster: 'ingestion' },
  { id: 'citation_verifier',label:'CITATION VER',     x: 1000, y: 540, cluster: 'ingestion' },
  { id: 'source_sanitizer',label: 'SRC SANITIZER',    x: 1000, y: 620, cluster: 'ingestion' },
  { id: 'source_synth',    label: 'SRC SYNTHESIZER',  x: 1000, y: 700, cluster: 'ingestion', model: 'anthropic/claude-sonnet-4-6' },

  // MOW WRITERS (y: 800-900) — 3 parallel
  { id: 'writer_a',        label: 'WRITER A\nCoverage', x: 600, y: 800, cluster: 'mow', model: 'anthropic/claude-opus-4-6' },
  { id: 'writer_b',        label: 'WRITER B\nArgument', x: 800, y: 800, cluster: 'mow', model: 'anthropic/claude-opus-4-6' },
  { id: 'writer_c',        label: 'WRITER C\nReadab.',  x: 1000,y: 800, cluster: 'mow', model: 'anthropic/claude-opus-4-6' },
  { id: 'writer_single',   label: 'WRITER SINGLE',    x: 1250, y: 800, cluster: 'standard', model: 'anthropic/claude-opus-4-6' },

  // POST-WRITE (y: 960-1160)
  { id: 'jury_multidraft', label: 'JURY MULTIDRAFT',  x: 800,  y: 960, cluster: 'mow' },
  { id: 'fusor',           label: 'FUSOR',             x: 800,  y: 1040,cluster: 'mow', model: 'openai/o3' },
  { id: 'post_draft_analyzer',label:'POST DRAFT ANA.', x: 1000, y: 960, cluster: 'postwrite', model: 'google/gemini-3.1-pro' },
  { id: 'researcher_targeted',label:'RESEARCHER TGT', x: 1200, y: 960, cluster: 'postwrite', model: 'perplexity/sonar-pro' },
  { id: 'style_linter',    label: 'STYLE LINTER',     x: 1000, y: 1060,cluster: 'postwrite' },
  { id: 'style_fixer',     label: 'STYLE FIXER',      x: 1200, y: 1060,cluster: 'postwrite', model: 'anthropic/claude-sonnet-4-6' },
  { id: 'metrics_collector',label:'METRICS COLL.',    x: 1000, y: 1160,cluster: 'postwrite' },
  { id: 'budget_controller',label:'BUDGET CTRL',      x: 1000, y: 1240,cluster: 'postwrite' },

  // JURY SYSTEM (y: 1340-1560)
  { id: 'jury',            label: 'JURY',              x: 1000, y: 1340,cluster: 'jury' },
  { id: 'r1',              label: 'R1',                x: 680,  y: 1440,cluster: 'jury', isJuryJudge: true, model: 'openai/o3' },
  { id: 'r2',              label: 'R2',                x: 740,  y: 1440,cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'r3',              label: 'R3',                x: 800,  y: 1440,cluster: 'jury', isJuryJudge: true, model: 'openai/o3-mini' },
  { id: 'f1',              label: 'F1',                x: 940,  y: 1440,cluster: 'jury', isJuryJudge: true, model: 'google/gemini-3.1-pro' },
  { id: 'f2',              label: 'F2',                x: 1000, y: 1440,cluster: 'jury', isJuryJudge: true, model: 'google/gemini-3.1-pro' },
  { id: 'f3',              label: 'F3',                x: 1060, y: 1440,cluster: 'jury', isJuryJudge: true, model: 'google/gemini-3.1-pro' },
  { id: 's1',              label: 'S1',                x: 1200, y: 1440,cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-sonnet-4-6' },
  { id: 's2',              label: 'S2',                x: 1260, y: 1440,cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },
  { id: 's3',              label: 'S3',                x: 1320, y: 1440,cluster: 'jury', isJuryJudge: true, model: 'anthropic/claude-haiku-3' },
  { id: 'aggregator',      label: 'AGGREGATOR',        x: 1000, y: 1560,cluster: 'jury' },

  // APPROVED PATH (y: 1660-1800)
  { id: 'context_compressor',label:'CTX COMPRESSOR',  x: 1000, y: 1660,cluster: 'approved', model: 'qwen/qwen3-7b' },
  { id: 'coherence_guard', label: 'COHERENCE GUARD',  x: 1000, y: 1740,cluster: 'approved', model: 'google/gemini-3.1-pro' },
  { id: 'section_checkpoint',label:'SECTION CKPT',   x: 1000, y: 1820,cluster: 'approved' },

  // REFLECTOR PATH (y: 1660-1940) — right branch
  { id: 'reflector',       label: 'REFLECTOR',         x: 1400, y: 1660,cluster: 'reflector', model: 'openai/o3' },
  { id: 'span_editor',     label: 'SPAN EDITOR',       x: 1300, y: 1760,cluster: 'reflector', model: 'anthropic/claude-sonnet-4-6' },
  { id: 'diff_merger',     label: 'DIFF MERGER',       x: 1300, y: 1840,cluster: 'reflector' },
  { id: 'await_human',     label: 'AWAIT HUMAN',       x: 1500, y: 1760,cluster: 'reflector', isHitlGate: true },

  // PANEL PATH — left branch
  { id: 'panel_discussion',label: 'PANEL DISC.',       x: 600,  y: 1660,cluster: 'panel' },

  // POST QA (y: 1940-2100)
  { id: 'post_qa',         label: 'POST QA',           x: 1000, y: 1940,cluster: 'postqa' },
  { id: 'length_adjuster', label: 'LENGTH ADJ.',       x: 1000, y: 2040,cluster: 'postqa' },

  // OUTPUT (y: 2160+)
  { id: 'publisher',       label: 'PUBLISHER',         x: 1000, y: 2160,cluster: 'output' },
  { id: 'feedback_collector',label:'FEEDBACK COLL.',   x: 1200, y: 2240,cluster: 'output' },

  // SHINE SATELLITE (right side, y: 800-1000)
  { id: 'shine_singleton', label: 'SHINE SINGLETON',   x: 1700, y: 800, cluster: 'shine', isSatellite: true },
  { id: 'shine_hypernetwork',label:'SHINE HYPERNET',   x: 1700, y: 880, cluster: 'shine', isSatellite: true },
  { id: 'shine_lora',      label: 'LORA WEIGHTS',      x: 1700, y: 960, cluster: 'shine', isSatellite: true },

  // RLM SATELLITE (right side, y: 1400-1560)
  { id: 'rlm_adapter',     label: 'RLM ADAPTER',       x: 1700, y: 1400,cluster: 'rlm', isSatellite: true },
  { id: 'deep_research_lm',label: 'DEEP RESEARCH LM',  x: 1700, y: 1480,cluster: 'rlm', isSatellite: true },
  { id: 'section_budget_guard',label:'SECTION BUDGET', x: 1700, y: 1560,cluster: 'rlm', isSatellite: true },
]
```

### File: `frontend/src/constants/pipeline-edges.ts`

Define ALL edges. Each edge has:
```ts
interface EdgeDefinition {
  id: string
  from: string
  to: string
  type: 'solid' | 'dashed' | 'dotted'    // solid=normal, dashed=conditional, dotted=satellite
  label?: string                           // condition label for dashed edges
  animated?: boolean                       // particle animation when active
}
```

Define all edges following the pipeline flow in `docs/UI_SPEC_FOR_AI_STUDIO.md` Section 2.

### File: `frontend/src/components/pipeline/AgentNode.tsx`

Props:
```ts
interface AgentNodeProps {
  definition: NodeDefinition
  state: NodeState
  onClick: () => void
  isSelected: boolean
}
```

Rendering rules:
- Position: `position: absolute; left: {x}px; top: {y}px; width: {width}px;`
- Shape: rectangle (default), diamond (isHitlGate), circle 32px (isJuryJudge)
- Background: cluster color from palette (very dark tint)
- Border color: based on state (see Section 1, visual language)
- Running state: CSS animation `pulse-glow` on box-shadow
- Satellite nodes (SHINE/RLM): dashed border, opacity 0.3 when inactive
- Label: node.label, font-size 11px, font-mono, text-drs-text
- Status dot: 8px circle, top-right corner
- Model badge: if node.model is set AND node is running/selected, show small model name below label

Running animation CSS (add to `globals.css`):
```css
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 4px var(--node-color); }
  50%       { box-shadow: 0 0 16px var(--node-color), 0 0 32px var(--node-color)40; }
}
```

### File: `frontend/src/components/pipeline/PipelineEdges.tsx`

Renders an SVG element that fills the full 2400×3200 canvas.
For each edge in `PIPELINE_EDGES`:
1. Calculate center-to-center path (straight line or bezier for curved edges like the loop-back)
2. Render `<path>` with appropriate stroke-dasharray
3. If `animated && isActive`: render `<circle r="4" fill={color}><animateMotion dur="1.5s" repeatCount="indefinite"><mpath href="#{edgeId}" /></animateMotion></circle>`

Edge is "active" when: the source node's status is `'running'`.

### File: `frontend/src/components/pipeline/PipelineMinimap.tsx`

160×100px fixed panel, bottom-right of canvas container.
Background: `drs-s2`. Border: `drs-border`.
- Scale factor: `160/2400 = 0.067` for X, `100/3200 = 0.031` for Y
- Render each node as a 3×2px colored rectangle (color = cluster color)
- Render viewport as a white/accent rectangle
- Click on minimap: pans the main canvas to that position
- Running nodes: pulse animation even on minimap

### File: `frontend/src/components/pipeline/PipelineHeader.tsx`

Fixed within canvas (not affected by zoom/pan), positioned at top:
```
[Topic: AI Safety Alignment]  •  §2/4  •  $0.23/$50  •  ████████░░░  42%
```
Show orange banner if `hardStopFired`. Show `⚠️ OSCILLAZIONE [{type}]` badge if `oscillationDetected`.

---

## 8. Right Panel — Agent Detail

### File: `frontend/src/components/panel/RightPanel.tsx`

Contextual panel. Content determined by `useAppStore.selectedNodeId`.
If no node selected: show run overview metrics (budget, CSS scores, counters).

#### When a node is selected:

**Header:**
```
[AGENT_NAME]  •  [status badge]
Model: claude-sonnet-4-6  [Cambia ▾]
```
The `[Cambia ▾]` dropdown shows all available models grouped by provider.
On selection: call `PATCH /api/runs/:docId/config` with `{ nodeId, newModel }`.
This changes the model for the NEXT invocation of that node (not retroactively).

**If status === 'running':**
```
OUTPUT LIVE
───────────
[streaming text in font-mono, autoscroll]

TOKEN & COSTO
Input:  2.847 tokens
Output: 412 / ~1.200 est.
Costo:  $0.014
```

**If status === 'completed':**
```
OUTPUT
──────
[collapsible — show first 200 chars, expand on click]

METRICS
Latency: 3.2s  •  In: 2.8k  •  Out: 1.1k  •  Cost: $0.014

PAYLOAD INPUT
▸ system_prompt (2.1k tok) [espandi]
▸ context (4.8k tok) [espandi]
▸ outline_section (340 tok) [espandi]
```

**Special case — JURY node:**
Show 3×3 verdict grid:
```
R1 [pass/fail] R2 [pass/fail] R3 [pass/fail]
F1 [pass/fail] F2 [VETO 🔴]  F3 [pass/fail]
S1 [pass/fail] S2 [pass/fail] S3 [pass/fail]
```
Each cell is clickable → expand reasoning text below grid.
Veto cells highlighted red with veto_category label.

**Special case — REFLECTOR node:**
Show feedback items list:
```
[HIGH] MISSING_EVIDENCE
"Section lacks peer-reviewed sources..."

[MEDIUM] SHALLOW_ANALYSIS
"Technical depth insufficient for..."
```
Each item has severity badge (red/yellow/orange) + expand for full text.

**Special case — RESEARCHER / RESEARCHER_TARGETED:**
Show sources list:
```
[0.92] arxiv.org/abs/2401.12345
Title: "Constitutional AI: Harmlessness..."
Snippet: "..."

[0.87] nature.com/articles/...
...
```
Reliability score badge (green >0.85, yellow 0.70-0.85, red <0.70).

---

## 9. HITL Components

### File: `frontend/src/components/hitl/HumanRequiredModal.tsx`

Triggers when SSE sends `HUMAN_REQUIRED`.
Full-screen overlay (`z-50`, background `rgba(0,0,0,0.8)`).
NOT dismissible by clicking outside or pressing Escape.

Content varies by `type`:
- `outline_approval` → `<OutlineDragList />`
- `section_approval` → `<SectionReviewSplit />`
- `escalation` → `<EscalationBanner />`

### File: `frontend/src/components/hitl/OutlineDragList.tsx`

Drag-and-drop outline editor using `@dnd-kit/core`.
Each section row has: drag handle, editable title (inline input), scope text, target_words number input, delete button.
Buttons: `+ Aggiungi Sezione`, `Approva Outline` (calls `POST /api/runs/:id/approve-outline`), `Rigenera`.

### File: `frontend/src/components/hitl/SectionReviewSplit.tsx`

Split view: left = draft with highlighted violations, right = reflector feedback.
Draft: rendered Markdown, violations highlighted with `<mark className="bg-yellow-900/40">` spans.
Feedback: sorted by severity (HIGH first). Each item: badge + text + "Fix suggerito" if available.
Sources below: list with reliability scores.
Buttons: `Approva`, `Rigenera`, `Modifica Manuale` (opens textarea overlay).

### File: `frontend/src/components/hitl/EscalationBanner.tsx`

Red banner with escalation type title.
Description of the conflict.
Three action buttons: `Risolvi Automatico`, `Modifica Manuale`, `Salta Sezione`.
Calls `POST /api/runs/:id/resolve-escalation` with selected action.

---

## 10. Backend API

### File: `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import runs, companion, metrics, settings

app = FastAPI(title="DRS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://frontend:80"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/api")
app.include_router(companion.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

@app.get("/health")
def health(): return {"status": "ok"}
```

### File: `backend/api/runs.py`

Implement ALL 10 endpoints from `docs/UI_SPEC_FOR_AI_STUDIO.md` Section 7:

```
POST   /api/runs                              → start new run
GET    /api/runs                              → list all runs
GET    /api/runs/{doc_id}                     → get run state
GET    /api/runs/{doc_id}/events              → SSE stream
POST   /api/runs/{doc_id}/approve-outline     → HITL outline
POST   /api/runs/{doc_id}/approve-section     → HITL section
POST   /api/runs/{doc_id}/resolve-escalation  → HITL escalation
GET    /api/runs/{doc_id}/output/{format}     → download file
DELETE /api/runs/{doc_id}                     → cancel run
PATCH  /api/runs/{doc_id}/config              → update node model
```

**SSE Implementation (`/api/runs/{doc_id}/events`):**
```python
from fastapi.responses import StreamingResponse
import asyncio, json

async def event_generator(doc_id: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"run:{doc_id}:events")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
            await asyncio.sleep(0)  # yield to event loop
    finally:
        await pubsub.unsubscribe(f"run:{doc_id}:events")

@router.get("/runs/{doc_id}/events")
async def stream_events(doc_id: str):
    return StreamingResponse(
        event_generator(doc_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
```

**Run Start (`POST /api/runs`):**
1. Validate body against `RunCreateRequest` Pydantic model
2. Generate `doc_id = str(uuid4())`
3. Save initial state to Redis: `SET run:{doc_id}:state {json} EX 86400`
4. Add to set: `SADD runs:all {doc_id}`
5. Save to PostgreSQL `runs` table
6. Start LangGraph pipeline in background: `asyncio.create_task(run_pipeline(doc_id, params))`
7. Return `{doc_id, status: "initializing"}`

### File: `backend/services/sse_broker.py`

The bridge between LangGraph pipeline and SSE clients.

```python
import redis.asyncio as redis
import json
from datetime import datetime

class SSEBroker:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def emit(self, doc_id: str, event_type: str, data: dict):
        payload = json.dumps({
            "event": event_type,
            "data": {**data, "ts": datetime.utcnow().isoformat()}
        })
        await self.redis.publish(f"run:{doc_id}:events", payload)
        # Also update persistent state in Redis
        await self._update_state(doc_id, event_type, data)

    async def _update_state(self, doc_id: str, event_type: str, data: dict):
        # Update the relevant field in run:{doc_id}:state based on event type
        state_key = f"run:{doc_id}:state"
        current = json.loads(await self.redis.get(state_key) or "{}")
        # ... update logic per event type
        await self.redis.set(state_key, json.dumps(current), ex=86400)
```

In each LangGraph node, import and call `broker.emit()` at start and end:
```python
# In every node wrapper:
async def researcher_node(state: DocumentState) -> DocumentState:
    await broker.emit(state.doc_id, "NODE_STARTED", {"node": "researcher"})
    # ... actual node logic ...
    await broker.emit(state.doc_id, "NODE_COMPLETED", {
        "node": "researcher",
        "duration_s": elapsed,
        "output": result_summary   # NOT the full output — just metadata
    })
    return state
```

### File: `backend/database/models.py`

SQLAlchemy model for PostgreSQL:
```python
class Run(Base):
    __tablename__ = "runs"
    doc_id = Column(String, primary_key=True)
    topic = Column(Text, nullable=False)
    quality_preset = Column(String(20))
    target_words = Column(Integer)
    max_budget = Column(Numeric(10,4))
    total_cost = Column(Numeric(10,6), default=0)
    total_words = Column(Integer)
    css_content = Column(Numeric(4,3))
    css_style = Column(Numeric(4,3))
    css_source = Column(Numeric(4,3))
    status = Column(String(30), default='initializing')
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
    output_paths = Column(JSONB)
```

---

## 11. Analytics Page

### File: `frontend/src/pages/Analytics.tsx`

Route: `/analytics`

Data source: `GET /api/analytics?from=&to=&preset=&keyword=`

Layout:
1. **Filter bar** (top): DateRangePicker + multi-select Preset + search keyword input
2. **KPI cards** (5 cards, horizontal row):
   - Runs completati
   - Costo medio per documento
   - Parole generate totali
   - CSS medio composito
   - Tasso successo prima iterazione
3. **Charts** (2×2 grid using Recharts):
   - `LineChart`: CSS score nel tempo (one line per doc)
   - `BarChart`: costo per preset (grouped)
   - `ScatterChart`: CSS vs costo (one dot per run, colored by preset)
   - Heatmap: iterazioni per sezione (use `ResponsiveContainer` + custom `Cell` grid)

All charts use DRS palette colors. Dark background charts with no gridlines except subtle ones.

---

## 12. Settings Page

### File: `frontend/src/pages/Settings.tsx`

Route: `/settings`

Sections:
1. **API Keys**: OpenRouter API key (password input with show/hide toggle)
2. **Model Assignments**: One row per agent, dropdown with all available OpenRouter models. Pre-populated from `docs/UI_SPEC_FOR_AI_STUDIO.md` Section 11 defaults.
3. **Default Config**: Default preset, default budget, default style profile
4. **Connectors**: Toggle for Perplexity Sonar / Tavily / Brave / Scraper
5. **Webhooks**: URL input + event type checkboxes

Save: `PUT /api/settings` — persists to PostgreSQL + `.env`

---

## 13. Docker Integration

### Update: `docker-compose.yml`

Add these two services to the existing file (DO NOT modify existing services):

```yaml
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: drs-backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://drs:${POSTGRES_PASSWORD:-drs_dev_password}@postgres:5432/drs
      REDIS_URL: redis://redis:6379
      MINIO_URL: http://minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER:-drs_admin}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD:-drs_secret_key}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: http://localhost:8000
    container_name: drs-frontend
    ports:
      - "3001:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

Also add Grafana datasource provisioning by creating:
- `config/grafana/provisioning/datasources/prometheus.yaml`
- Mount it in the existing `grafana` service:
  ```yaml
  volumes:
    - ./config/grafana/provisioning:/etc/grafana/provisioning:ro  # ADD THIS
    - ./config/grafana_dashboard.json:/var/lib/grafana/dashboards/drs.json:ro
    - grafana_data:/var/lib/grafana
  ```

### File: `backend/Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN alembic upgrade head
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### File: `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### File: `frontend/nginx.conf`

```nginx
server {
    listen 80;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;  # SPA routing
    }
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;           # Critical for SSE
        proxy_cache off;
        chunked_transfer_encoding on;
    }
}
```

---

## 14. Dependencies

### `frontend/package.json` — key dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "zustand": "^4.5.0",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0",
    "recharts": "^2.12.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "framer-motion": "^11.3.0",
    "eventsource-parser": "^1.1.2"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^3.4.0",
    "@tailwindcss/typography": "^0.5.13",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "vitest": "^1.6.0",
    "@playwright/test": "^1.45.0",
    "@testing-library/react": "^16.0.0"
  }
}
```

### `backend/requirements.txt`

```
fastapi==0.111.0
uvicorn[standard]==0.30.0
redis[hiredis]==5.0.7
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.31
alembic==1.13.2
pydantic==2.8.0
python-multipart==0.0.9
httpx==0.27.0
minio==7.2.7
prometheus-client==0.20.0
```

---

## 15. Implementation Order

Follow this exact sequence. Each step depends on the previous.

```
STEP 1  — Project scaffolding
        frontend/ (Vite + React + TS + Tailwind)
        backend/ (FastAPI skeleton)
        Update docker-compose.yml

STEP 2  — Design System
        tailwind.config.ts with full DRS palette
        globals.css with @keyframes
        All base components: StatusBadge, ProgressBar,
        CSSGauge, BudgetGauge, ModelBadge

STEP 3  — State layer
        useAppStore, useConversationStore, useRunStore
        useSSE hook (with mock events for testing)

STEP 4  — AppShell + Layout
        AppShell, Topbar, DocumentSidebar, ChatInput
        Routing setup (react-router-dom)
        Settings page (simplest, no SSE dependency)

STEP 5  — Backend core
        Database models + Alembic migration
        Run CRUD endpoints
        SSE broker + streaming endpoint
        Companion chat endpoint

STEP 6  — Chat Interface
        ChatThread, ChatMessage, SuggestionChips
        Connect to POST /api/companion/chat
        Connect to POST /api/runs (trigger from companion action)

STEP 7  — Pipeline Canvas (biggest step)
        pipeline-layout.ts (all 42 nodes + coordinates)
        pipeline-edges.ts (all edges)
        PipelineCanvas (pan+zoom)
        AgentNode (all shapes + states)
        PipelineEdges (SVG + particle animations)
        PipelineMinimap
        PipelineHeader
        ShineCluster + RlmCluster satellites

STEP 8  — Right Panel
        RightPanel (context-driven)
        AgentLogPanel (streaming)
        TokenMeter
        JuryVerdictGrid
        SourceList
        PayloadTree
        AgentModelDropdown → PATCH /api/runs/:id/config

STEP 9  — Document Preview
        Document Markdown renderer
        Section expand/collapse in sidebar
        Chapter export buttons

STEP 10 — HITL Components
        HumanRequiredModal
        OutlineDragList
        SectionReviewSplit
        EscalationBanner

STEP 11 — Analytics page
        All 4 charts with Recharts
        Filter bar
        GET /api/analytics endpoint

STEP 12 — Docker + Integration
        backend/Dockerfile, frontend/Dockerfile
        nginx.conf
        Grafana provisioning YAML
        Full docker compose up smoke test

STEP 13 — Testing
        Vitest unit tests for all stores
        Vitest component tests for design system
        Playwright E2E: 5 critical scenarios
```

---

## 16. Critical Notes for AI Agent

1. **DO NOT use React Flow, D3, or any graph library.** Pipeline canvas is SVG + absolute positioned divs with hardcoded coordinates. The DRS pipeline topology is FIXED.

2. **DO NOT use any component library** (MUI, Chakra, Radix, shadcn). All components are custom Tailwind.

3. **ChatInput is ALWAYS visible.** It is mounted in AppShell and never unmounted. It survives route changes, state changes, modal overlays.

4. **SSE is the source of truth** for pipeline state — not polling. The `useSSE` hook must handle auto-reconnect.

5. **Companion agent starts runs.** There is NO dedicated "New Document" form page. The companion collects all needed info conversationally and emits `START_RUN` action.

6. **HITL modal is blocking.** `HUMAN_REQUIRED` SSE event triggers a full-screen overlay that cannot be dismissed until the user takes action.

7. **Pipeline canvas survives view switches.** When user switches from Pipeline View to Chat View (keyboard shortcut K), `PipelineCanvas` uses `visibility: hidden` — NOT unmounted — to preserve animation state.

8. **Satellite clusters** (SHINE, RLM) are rendered at 30% opacity when inactive. They show the architecture exists but is off. Toggle to activate them affects next pipeline run.

9. **Right panel model dropdown** changes the model for the NEXT invocation of that node, not retroactively. Update the run config via `PATCH /api/runs/:id/config`.

10. **All SSE events include `ts` (ISO 8601 timestamp).** Use it for the pipeline stepper timing display.

11. **For the Jury expanded view:** when the user's viewport is near the JURY cluster and they click it, expand it in-place on the canvas (not in the right panel). The expanded jury shows the 3×3 judge grid with verdicts.

12. **Minimap interaction:** clicking a position on the minimap pans the main canvas to center that point in the viewport.

---

## 17. File Tree — Complete

```
frontend/
├── Dockerfile
├── nginx.conf
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── globals.css
    ├── constants/
    │   ├── pipeline-layout.ts     # 42 node definitions + coordinates
    │   ├── pipeline-edges.ts      # All edge definitions
    │   └── models.ts              # Available OpenRouter models list
    ├── store/
    │   ├── useAppStore.ts
    │   ├── useConversationStore.ts
    │   └── useRunStore.ts
    ├── hooks/
    │   ├── useSSE.ts
    │   ├── usePanZoom.ts
    │   └── useKeyboardShortcuts.ts
    ├── types/
    │   ├── run.ts
    │   ├── pipeline.ts
    │   └── api.ts
    ├── lib/
    │   └── api.ts                 # Typed API client (fetch wrapper)
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.tsx
    │   │   ├── Topbar.tsx
    │   │   ├── DocumentSidebar.tsx
    │   │   ├── SectionItem.tsx
    │   │   ├── ChatInput.tsx
    │   │   ├── MainArea.tsx
    │   │   └── RightPanel.tsx
    │   ├── chat/
    │   │   ├── ChatThread.tsx
    │   │   ├── ChatMessage.tsx
    │   │   └── SuggestionChips.tsx
    │   ├── pipeline/
    │   │   ├── PipelineCanvas.tsx
    │   │   ├── PipelineHeader.tsx
    │   │   ├── PipelineEdges.tsx
    │   │   ├── AgentNode.tsx
    │   │   ├── PipelineMinimap.tsx
    │   │   ├── ShineCluster.tsx
    │   │   └── RlmCluster.tsx
    │   ├── panel/
    │   │   ├── AgentLogPanel.tsx
    │   │   ├── TokenMeter.tsx
    │   │   ├── JuryVerdictGrid.tsx
    │   │   ├── SourceList.tsx
    │   │   ├── PayloadTree.tsx
    │   │   └── AgentModelDropdown.tsx
    │   ├── hitl/
    │   │   ├── HumanRequiredModal.tsx
    │   │   ├── OutlineDragList.tsx
    │   │   ├── SectionReviewSplit.tsx
    │   │   └── EscalationBanner.tsx
    │   ├── document/
    │   │   ├── DocumentPreview.tsx
    │   │   └── ChapterExportMenu.tsx
    │   └── ui/
    │       ├── StatusBadge.tsx
    │       ├── PresetBadge.tsx
    │       ├── ProgressBar.tsx
    │       ├── CSSGauge.tsx
    │       ├── BudgetGauge.tsx
    │       ├── RunCard.tsx
    │       └── ModelSelector.tsx
    └── pages/
        ├── Analytics.tsx
        └── Settings.tsx

backend/
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── main.py
├── api/
│   ├── runs.py
│   ├── companion.py
│   ├── metrics.py
│   └── settings.py
├── services/
│   ├── sse_broker.py
│   ├── run_manager.py
│   └── minio_service.py
├── database/
│   ├── connection.py
│   ├── models.py
│   └── migrations/
├── prompts/
│   └── companion_system.txt
└── config/
    └── settings.py            # Pydantic Settings from env vars

config/
├── grafana_dashboard.json     # already exists
├── prometheus.yml             # already exists
└── grafana/
    └── provisioning/
        └── datasources/
            └── prometheus.yaml  # NEW — auto-provision Prometheus datasource
```

---

*Reference documents:*
- *Full API + SSE spec: `docs/UI_SPEC_FOR_AI_STUDIO.md`*
- *Pipeline architecture: same file, Section 2*
- *Agent model assignments: same file, Section 11*
- *Quality preset parameters: same file, Section 8*
- *Infrastructure: `docker-compose.yml`*

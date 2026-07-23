# Frontend Restyle — Design

## Goal

The frontend (`frontend/`) is functionally complete per `tasks.md`'s Frontend
phases but entirely unstyled (plain divs/buttons, no CSS at all). This
project restyles it with Tailwind + shadcn/ui, and folds in one layout
change: replacing the hard setup/workspace screen switch with a single
continuous chat-first screen.

## Screen model (replaces current behavior)

Today, `SessionContext`'s `screen: "setup" | "workspace"` field hard-switches
between `SetupScreen.tsx` (stacked, unstyled upload/prompt/generate controls)
and `WorkspaceScreen.tsx` (chart + chat side by side), flipping only after
`POST /generate` succeeds (`GENERATED` action).

New behavior — one continuous screen, no screen switch:

- **No chart uploaded yet:** the chat panel fills the full width and is the
  only thing on screen. A compact toolbar near the chat input holds icon
  buttons: upload chart, upload evidence, system prompt (gear icon, opens a
  dialog), and Generate (disabled until both uploads exist).
- **Chart uploaded:** a chart panel slides in on the left (~55-60% width),
  chat shrinks to the right (~40-45%). This triggers on chart upload itself
  (`CHART_UPLOADED`), not on `GENERATED` — the backend already returns rows
  with `confidence: null` right after upload (per `tasks.md` Phase 3), so the
  chart panel has real content to show before Generate is even clicked.
  Layout stays this way for the rest of the session.

Consequences for existing code:

- `SetupScreen.tsx` is removed. Its contents (`UploadChartButton`,
  `UploadEvidenceButton`, `SystemPromptEditor`, `GenerateButton`) become
  compact icon-trigger versions living in a new `ChatToolbar.tsx`, rendered
  as part of the chat panel rather than a separate screen.
- `WorkspaceScreen.tsx` is replaced by a single top-level layout component
  (e.g. `MainScreen.tsx`) that always renders the chat panel and
  conditionally renders the chart panel based on `state.chartUploaded`,
  animating/transitioning the width split.
- `SessionContext`'s `Screen` type and `screen` field are removed. Layout
  derives directly from `chartUploaded`. `GENERATED` no longer needs to set
  `screen: "workspace"`.
- `App.tsx`'s top-level render (`state.screen === "setup" ? ... : ...`)
  simplifies to always rendering `MainScreen`.

## Visual design

- **Palette:** neutral gray scale as the base (no pure black) — grays for
  body text, borders, and secondary buttons. Soft pastel tints (gray-blue /
  lavender-gray) for panel surfaces such as the chat window background,
  distinguishing panels from the page background without hard borders.
  Primary actions (Generate, Accept, Export, Send) use a dark charcoal gray
  for contrast against the pastel surfaces.
- **Confidence badges:** Strong/Moderate/Weak rows in the chart panel use
  pastel traffic-light colors (soft green/amber/red). Flagged rows get a
  soft red/orange banner. This is the one place saturated/semantic color
  appears in the UI — everywhere else stays gray/pastel-neutral.
- **Typography:** Tailwind's default sans stack (Inter-based), comfortable
  line-height for evidence/reasoning text blocks in chart rows.
- **Dark mode:** out of scope for now — light mode only. Using Tailwind/CSS
  variable tokens from the start keeps a future dark theme low-cost, but no
  dark theme is built in this pass.

## Tech approach

- Install and configure Tailwind CSS + shadcn/ui in `frontend/`
  (`components.json`, `src/components/ui/`, `tailwind.config`, CSS variables
  for the gray + pastel theme, replacing shadcn's default blue-leaning
  theme).
- Use shadcn primitives across the app: `Button`, `Card`, `Badge`, `Input`,
  `Textarea`, `Dialog` (system prompt editor), `Tooltip` (icon buttons),
  `ScrollArea` (chat message list / chart row list).
- Restyle every existing component in place (`ChartPanel/*`, `ChatPanel/*`,
  `GenerateButton`, `UploadChartButton`, `UploadEvidenceButton`,
  `SystemPromptEditor`) using shadcn primitives and Tailwind utility classes
  — no bespoke CSS files.
- New files needed for the layout change: `ChatToolbar.tsx` (compact icon
  buttons), `MainScreen.tsx` (replaces `WorkspaceScreen.tsx`). `SetupScreen.tsx`
  is deleted.
- No backend changes. No changes to `SessionContext` actions/data shape
  beyond removing the `screen` field and its one usage.

## Out of scope

- Dark mode.
- Any new features beyond what's already wired (accept/reject/undo/flag/
  export/chat all already work functionally — this pass is visual +
  the one layout change above).
- Animation polish beyond a simple width-transition when the chart panel
  appears.

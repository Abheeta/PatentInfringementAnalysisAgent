# Lumenci Assistant — Frontend Design Doc

Derived from `docs/user-flow-steps.md`, `docs/user-flow-diagram.md`, and
`docs/superpowers/specs/2026-07-21-claim-chart-chat-refinement-design.md` (PRD).
This document covers the React frontend for the prototype. See
`docs/superpowers/specs/2026-07-22-backend-design.md` for the backend API
this talks to, including the `session_id` model that every call is scoped
by.

**Stack:** React + Vite, plain fetch calls to the FastAPI backend (no
client-side router needed — single-screen app with a setup/chat mode
switch), React Context + `useReducer` for shared state.

**Component tree**
```
App
 ├─ SetupScreen                (shown until /generate has run for this session)
 │    ├─ UploadChartButton       → POST /session/{sid}/upload-chart
 │    ├─ UploadEvidenceButton     → POST /session/{sid}/upload-evidence (files and/or a link; repeatable)
 │    ├─ SystemPromptEditor        (freeform textarea)
 │    └─ GenerateButton              → POST /session/{sid}/generate (disabled until chart is uploaded)
 └─ WorkspaceScreen              (split-pane, shown once generated=true)
      ├─ ChartPanel (left)
      │    └─ ChartRow[]           (claim element / evidence / reasoning / confidence badge)
      │         ├─ PendingBanner     (shown when row.pending_value != null: Accept/Reject/Modify)
      │         ├─ UndoButton         (enabled iff row.previous_* triplet is non-null)
      │         └─ FlagIcon
      └─ ChatPanel (right)
           ├─ SettingsButton → SystemPromptEditor (reopened as modal/drawer)
           ├─ MessageList
           ├─ RowChip                (renders inline in a message when row-anchored)
           ├─ ChatInput               (@Row chip insertion on row click / Modify / Flag)
           └─ ExportButton            (always enabled, visible in chat header)
```

A session is created (`POST /session`) the moment the app loads with no
stored `session_id`; the returned id is kept in memory (and `localStorage`,
so a reload doesn't lose it) and attached to every subsequent request. The
three `SetupScreen` actions can be used in any order the analyst wants to
click the first two buttons, but the backend enforces `upload-chart` before
`upload-evidence`/`generate` (see backend doc §2) — the frontend mirrors
this by disabling `UploadEvidenceButton` and `GenerateButton` until
`upload-chart` has succeeded. `UploadEvidenceButton` stays enabled and
clickable repeatedly after that, so the analyst can add files/links in
multiple batches before clicking Generate.

**State shape (Context + reducer)**
```ts
{
  sessionId: string | null,           // set immediately on app load via POST /session
  chartUploaded: boolean,
  generated: boolean,
  chart: { rows: Row[] } | null,       // populated once /generate responds
  chatMessages: ChatMessage[],
  pendingRowId: number | null,           // which row's @Row chip is staged in the input box
  systemPromptDraft: string,
  screen: 'setup' | 'workspace'
}
```
Actions: `SESSION_CREATED`, `CHART_UPLOADED`, `EVIDENCE_UPLOADED`,
`GENERATED` (carries the initial rows + opening chat message),
`ROW_UPDATED` (accept/reject/undo/pending-set), `MESSAGE_SENT`,
`MESSAGE_RECEIVED`, `ROW_CHIP_STAGED`, `SYSTEM_PROMPT_SAVED`. All
server-confirmed mutations (accept/reject/undo/flag/chat) go through fetch
→ on success, dispatch the reducer action with the server's returned
row/message state (server is source of truth, no optimistic-only state
that could drift from SQLite).

**Key interaction wiring**
- On app load: if no `sessionId` in `localStorage`, call `POST /session` and store the result before rendering `SetupScreen`.
- **UploadChartButton** posts the CSV file to `/session/{sid}/upload-chart`; on success, dispatches `CHART_UPLOADED` and enables the other two `SetupScreen` actions.
- **UploadEvidenceButton** opens a small picker for either file(s) or a URL text field, posts to `/session/{sid}/upload-evidence`; repeatable, each call just dispatches `EVIDENCE_UPLOADED` (no chart re-render needed since evidence isn't shown in the chart panel).
- **GenerateButton** posts to `/session/{sid}/generate` (disabled until chart upload succeeds); on success, dispatches `GENERATED` with the classified rows + opening chat message, and switches `screen` to `'workspace'`.
- Clicking a chart row or its **Modify** button dispatches `ROW_CHIP_STAGED(row.id)`, which prepends a non-removable `@Row[n]` chip token to `ChatInput`'s current value; submitting sends `{content, row_id}` to `/session/{sid}/chat/message`.
- **Accept/Reject** call their row endpoints directly (no chat message involved) and just re-render that row from the response.
- **Undo** opens a lightweight confirm dialog (plain component, no library needed) before calling `/session/{sid}/rows/{id}/undo`.
- **Flag** calls `/session/{sid}/rows/{id}/flag`, then stages that row's chip in chat input (same mechanism as Modify) so the analyst can describe the issue in their next message.
- **Export** is a plain `<a href="/session/{sid}/export">` / fetch-blob-and-download — no state dependency, works once `generated` is true.

**Testing** — no formal test suite planned for the prototype; manual
click-through of the full flow (create session → upload chart → upload
evidence → set system prompt → generate → chat loop →
accept/reject/modify/undo/flag → export) is the acceptance bar, consistent
with the PRD's prototype framing.

# Lumenci Assistant — Implementation Tasks (High Level)

Companion to `docs/superpowers/specs/2026-07-23-project-structure.md` (file
layout) and the ai/backend/frontend design docs it's derived from. This is
the build order, not per-file detail — each phase names the files it
touches and what "done" looks like, so implementation can proceed phase by
phase without re-deriving sequencing each time.

Backend is built first, end to end, before frontend — the frontend has
nothing to call until the API exists. Build order: DB → upload/session →
every endpoint reachable with AI stubbed (dummy values, no LLM calls) →
full frontend build against the stubbed backend → swap stubs for real AI
calls (separate section at the end of this file, after Frontend).

**Stub contract:** each stubbed feature function in `ai/features/` must
have the exact call signature the real implementation will have (same
args, same return shape matching ai-design.md §6's schemas). Routers and
services call these functions and must not change at all when stubs are
later replaced with real LLM calls — only the inside of each `ai/
features/*.py` file changes.

## Backend

- [ ] **Phase 1 — Scaffolding.** `requirements.txt` (fastapi, uvicorn,
  httpx, beautifulsoup4, python-docx, pytest), `app/main.py` (empty
  FastAPI app boots), `app/config.py` (env vars: `LLM_PROVIDER`, Ollama
  host/model, OpenRouter key/model, SQLite path), `app/errors.py`
  (`ApiError` + exception handler producing `{"error": {code,message}}`).
  Done when `uvicorn app.main:app` starts with no routes.

- [ ] **Phase 2 — Database layer.** `app/db/schema.sql` (all four tables
  from backend-design §2, including `flagged`/`pending_*`/`previous_*`),
  `app/db/connection.py` (opens the SQLite file, runs the schema on first
  boot). Done when a throwaway script can insert/read a `sessions` row.

- [ ] **Phase 3 — Sessions + chart upload.** `services/session_service.py`
  (`create_session`, `get_session`), `routers/session_router.py`
  (`POST /session`), `services/chart_service.py`'s `parse_chart_csv` (only
  — accept/reject/undo/flag come later) and `get_rows`,
  `routers/upload_router.py`'s chart half, `routers/chart_router.py`'s
  `GET /chart`. Covers upload validation: `invalid_file_type`,
  `malformed_csv`, `file_too_large`, `chart_already_exists`. Done when you
  can create a session, upload a real 3-column CSV, and `GET /chart`
  returns the parsed rows with `confidence: null`.

- [ ] **Phase 4 — Evidence upload.** `services/evidence_service.py`
  (`store_uploaded_text`, `fetch_url` via httpx+BeautifulSoup,
  `get_evidence_pool`), evidence half of `upload_router.py`. Covers
  `chart_not_uploaded`, `invalid_file_type`, `file_too_large`,
  `invalid_request`, `url_fetch_failed`. Done when both a `.txt` upload
  and a real URL populate `evidence_docs` for a session.

- [ ] **Phase 5 — Stub AI layer.** `ai/schemas.py` (disambiguation/
  proposal/classification schemas from ai-design §6, kept as the shape
  reference even though nothing enforces them yet), and dummy
  implementations of `ai/features/initial_classification.py`,
  `ai/features/disambiguation.py`, `ai/features/refinement_proposal.py`,
  `ai/features/regrounded_correction.py` — each returns fixed/canned
  values matching its real output schema with no LLM call at all (e.g.
  classification always tiers rows in a repeating Strong/Moderate/Weak
  pattern; disambiguation always resolves to the first row id it's given
  a message about, or a canned clarifying question if none was tagged;
  refinement proposal returns a fixed dummy value/reasoning/confidence;
  regrounded correction returns a fixed dummy "verbatim-looking" string).
  No `ai/provider.py`, `ai/baseline_prompt.py`, or `ai/validation.py` yet
  — nothing here calls out to Ollama/OpenRouter. Done when each stub
  function, called directly, returns schema-shaped dummy data.

- [ ] **Phase 6 — Generate endpoint (stubbed).** `ai/features/
  opening_message.py` (template, no LLM call — this one's real
  implementation from the start, per ai-design §6.4), `POST /generate` in
  `chart_router.py` (calls the stub classification, writes `confidence`
  per row, sets `generated=1`, returns the opening message). Done when
  `/generate` against a real chart+evidence writes dummy confidence tiers
  to every row and returns a correctly-composed opening message.

- [ ] **Phase 7 — Chat message flow (stubbed).**
  `services/chat_service.py`'s `handle_message` (resolve→propose
  orchestration calling the stub disambiguation/refinement-proposal
  functions, field-name mapping onto `pending_*`), `routers/
  chat_router.py`. Done when a chat message with an explicit `row_id`
  produces a dummy pending proposal, and one with no `row_id` either
  resolves (via the stub) or returns the canned clarifying question.

- [ ] **Phase 8 — Row mutation endpoints.** `accept`/`reject`/`undo` in
  `chart_service.py`, `routers/row_router.py`. No AI involved. Covers
  `no_pending_proposal` and `no_undo_available`. Done when the full
  accept→undo round trip works against a row with a live pending
  proposal.

- [ ] **Phase 9 — Flag + re-grounded correction (stubbed).**
  `set_flagged`/`clear_flagged` in `chart_service.py`, flag branch wired
  into `chat_service.handle_message` (calls the stub regrounded-
  correction function), flag endpoint in `row_router.py`,
  `chat_service.post_flag_system_note`. Done when flagging a row then
  sending a follow-up message produces the dummy verbatim-style
  correction (or a clean `no_evidence_found`, whichever the stub is
  driven to return) and clears `flagged`.

- [ ] **Phase 10 — System prompt + export.**
  `routers/system_prompt_router.py` (get/put), `services/
  export_service.py`'s `build_docx` (using `product_feature`, never
  `pending_value`), `routers/export_router.py`. No AI involved. Done when
  a `.docx` downloads with the right columns/confidence for a chart that
  has an unresolved pending proposal on at least one row.

- [ ] **Phase 11 — Backend integration check (stubbed AI).** Fill in
  `tests/test_chart_service.py`, `test_csv_parsing.py`, `test_export.py`,
  `test_url_fetch.py` against the stub features. Then one manual
  end-to-end run through the whole flow — upload → generate → chat →
  accept/reject/undo/flag → export — entirely against stubbed AI. This is
  the point the backend is "done" for frontend purposes: every endpoint
  in api-contracts.md works, just with dummy AI content.

## Frontend

Backend must be reachable through Phase 11 above (every endpoint working
against stubbed AI) before this is worth wiring up end to end, though
scaffolding/state can start earlier in parallel. The frontend is built and
fully clicked-through against stubbed AI content — it has no way to tell
the difference, since stub output already matches the real schemas.

- [ ] **Phase 1 — Scaffolding.** `package.json`, `vite.config.js`,
  `src/main.tsx`, `src/App.tsx` (renders nothing but a placeholder yet).
  Done when `npm run dev` serves a blank page.

- [ ] **Phase 2 — API client + types.** `src/types/index.ts` (`Row`,
  `ChatMessage`, `ApiError`), `src/api/client.ts` (one function per
  backend endpoint from api-contracts.md, parses the error envelope).
  Done when a throwaway call to `createSession()` against the running
  backend returns a real `session_id`.

- [ ] **Phase 3 — Session state.** `src/context/SessionContext.tsx`
  (state shape + reducer + all actions from frontend-design). Wire
  `App.tsx`'s mount logic: read `sessionId` from `localStorage`, call
  `createSession()` if absent, store it. Done when reloading the page
  reuses the same session instead of creating a new one.

- [ ] **Phase 4 — Setup screen.** `components/SetupScreen.tsx`,
  `UploadChartButton.tsx`, `UploadEvidenceButton.tsx`,
  `SystemPromptEditor.tsx`, `GenerateButton.tsx`, wired to the real
  backend (upload-chart, upload-evidence, system-prompt, generate). Done
  when clicking through all four setup actions against a live backend
  ends with `screen` flipping to `'workspace'`.

- [ ] **Phase 5 — Chart panel (read-only first).**
  `WorkspaceScreen.tsx`, `ChartPanel/ChartPanel.tsx`,
  `ChartPanel/ChartRow.tsx` rendering claim element / evidence /
  reasoning / confidence badge from `GET /chart` — no
  pending/flag/undo controls yet. Done when a generated chart's rows
  render correctly in the left pane.

- [ ] **Phase 6 — Chat panel.** `ChatPanel/ChatPanel.tsx`,
  `MessageList.tsx`, `ChatInput.tsx`, `RowChip.tsx`, wired to
  `POST /chat/message`; row click / `@Row` chip staging via
  `ROW_CHIP_STAGED`. Done when typing a message with no row produces
  either a clarifying question or a proposal, visible in the chat.

- [ ] **Phase 7 — Row action controls.** `PendingBanner.tsx` (Accept/
  Reject/Modify), `UndoButton.tsx`, `FlaggedBanner.tsx`, `FlagIcon.tsx`,
  including the silent-refetch-on-409 behavior for stale UI. Done when
  the full accept/reject/modify/undo/flag cycle works against the chart
  panel end to end.

- [ ] **Phase 8 — Settings + export.** `SettingsButton.tsx` (reopens
  `SystemPromptEditor` mid-workspace), `ExportButton.tsx`. Done when a
  mid-session system-prompt edit saves correctly and Export downloads a
  real `.docx`.

- [ ] **Phase 9 — Full manual click-through.** One complete run of the
  acceptance flow from frontend-design's testing section: create session
  → upload chart → upload evidence → set system prompt → generate → chat
  loop → accept/reject/modify/undo/flag → export. No formal test suite
  planned for the prototype, per that doc. Still running against stubbed
  AI at this point.

## Backend — AI Integration (replace stubs)

Once the frontend is fully working end to end against stubbed AI, swap
the stubs for real LLM calls. Routers, services, and the frontend do not
change in this section — only what's inside `ai/features/*.py`.

- [ ] **Phase 12 — LLM provider abstraction.** `ai/provider.py`
  (`LLMProvider` interface, `OllamaProvider`, `OpenRouterProvider`,
  `LLMUnavailableError`), plus `tests/fakes.py`'s `FakeProvider` for
  everything downstream. Done when a manual script can call
  `OllamaProvider.generate(messages, schema)` against a running local
  Ollama and get back schema-shaped JSON.

- [ ] **Phase 13 — Baseline prompt + validation.**
  `ai/baseline_prompt.py` (verbatim ai-design §5 text), `ai/
  validation.py` (pairing rules, full-row-set check, verbatim-quote
  check) built against the schemas already defined in Phase 5's
  `ai/schemas.py`. Done when unit tests using `FakeProvider` confirm each
  validation rule fires correctly on both valid and invalid canned
  responses.

- [ ] **Phase 14 — Replace stub features with real ones.** Rewrite
  `ai/features/initial_classification.py`, `disambiguation.py`,
  `refinement_proposal.py`, and `regrounded_correction.py` in place: same
  function signatures as the Phase 5 stubs, but now building the real
  prompt (baseline + analyst system prompt + task instruction + context
  per ai-design §6), calling `LLMProvider.generate`, and running the
  Phase 13 validation (with the retry-once-then-error / converge-to-
  `no_evidence_found` behavior ai-design §4/§6.5 specify). Done when
  `/generate`, chat, and flag flows all produce real model output through
  the exact same call sites wired in Phases 6/7/9 — no router or service
  changes needed.

- [ ] **Phase 15 — Test pass + integration check.** Fill in/extend
  `tests/test_chart_service.py`, `test_csv_parsing.py`, `test_export.py`,
  `test_url_fetch.py` against `FakeProvider` (per backend-design's
  testing strategy). Then one manual end-to-end run through the whole
  flow — upload → generate → chat → accept/reject/undo/flag → export —
  against real Ollama, then again against OpenRouter.

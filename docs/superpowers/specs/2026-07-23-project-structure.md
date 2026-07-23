# Lumenci Assistant — Project Structure

Derived from `docs/superpowers/specs/2026-07-22-frontend-design.md`,
`docs/superpowers/specs/2026-07-22-backend-design.md`,
`docs/superpowers/specs/2026-07-23-ai-design.md`,
`docs/superpowers/specs/2026-07-22-api-contracts.md`, and
`docs/user-flow-steps.md`. This doc maps those designs onto an actual
directory/file layout, with each file's responsibilities at the method/
service level. It does not introduce new decisions — anything below that
looks like a decision is just naming a structure the other docs already
imply.

`frontend/` and `backend/` are separate top-level folders (separate
deploy/run units, per backend-design §1's architecture diagram). `ai/`
lives *inside* `backend/app/` rather than as a third top-level folder:
per ai-design §1, there is no separate AI service or agent framework —
it's plain Python functions called in-process from FastAPI through one
`LLMProvider` interface. Giving it its own subfolder keeps LLM-specific
code (prompts, schemas, provider calls) visibly separated from routing/
persistence code without implying a service boundary that doesn't exist.

```
project-root/
├── frontend/
├── backend/
└── docs/                (existing)
```

## frontend/

React + Vite, plain `fetch`, Context + `useReducer`. No router (single-
screen app with a setup/workspace mode switch per frontend-design).

```
frontend/
├── package.json
├── vite.config.js
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   └── client.ts
    ├── context/
    │   └── SessionContext.tsx
    ├── types/
    │   └── index.ts
    └── components/
        ├── SetupScreen.tsx
        ├── UploadChartButton.tsx
        ├── UploadEvidenceButton.tsx
        ├── SystemPromptEditor.tsx
        ├── GenerateButton.tsx
        ├── WorkspaceScreen.tsx
        ├── ChartPanel/
        │   ├── ChartPanel.tsx
        │   ├── ChartRow.tsx
        │   ├── PendingBanner.tsx
        │   ├── FlaggedBanner.tsx
        │   ├── UndoButton.tsx
        │   └── FlagIcon.tsx
        └── ChatPanel/
            ├── ChatPanel.tsx
            ├── SettingsButton.tsx
            ├── MessageList.tsx
            ├── RowChip.tsx
            ├── ChatInput.tsx
            └── ExportButton.tsx
```

**`main.tsx`** — Renders `<App />` wrapped in `SessionContext`'s provider.

**`App.tsx`** — On mount: reads `sessionId` from `localStorage`; if absent,
calls `api/client.createSession()` and stores the result before first
render. Renders `SetupScreen` while `state.screen === 'setup'`,
`WorkspaceScreen` while `'workspace'`.

**`api/client.ts`** — One function per backend endpoint, all taking/
returning plain objects matching api-contracts.md shapes; every call
attaches `sessionId` as `{sid}` in the URL. Functions: `createSession()`,
`uploadChart(sid, file)`, `uploadEvidence(sid, {file|url})`,
`getChart(sid)`, `generate(sid)`, `sendChatMessage(sid, {content, row_id})`,
`acceptRow(sid, rowId)`, `rejectRow(sid, rowId)`, `undoRow(sid, rowId)`,
`flagRow(sid, rowId)`, `getSystemPrompt(sid)`, `putSystemPrompt(sid, text)`,
`exportChart(sid)` (returns a blob for download). Parses the
`{"error": {"code","message"}}` envelope on non-2xx and throws a typed
error the reducer/components can branch on.

**`context/SessionContext.tsx`** — Holds the state shape from
frontend-design §"State shape": `sessionId`, `chartUploaded`, `generated`,
`chart`, `chatMessages`, `pendingRowId`, `systemPromptDraft`, `screen`.
Reducer handles actions `SESSION_CREATED`, `CHART_UPLOADED`,
`EVIDENCE_UPLOADED`, `GENERATED`, `ROW_UPDATED`, `MESSAGE_SENT`,
`MESSAGE_RECEIVED`, `ROW_CHIP_STAGED`, `SYSTEM_PROMPT_SAVED` — each simply
merges server-confirmed state into the tree; no client-only derived state
that could drift from SQLite.

**`types/index.ts`** — `Row`, `ChatMessage`, `ApiError` types mirroring
api-contracts.md's `GET /chart` row shape and chat message shape.

**`components/SetupScreen.tsx`** — Renders the three setup actions plus
`SystemPromptEditor`; disables `UploadEvidenceButton`/`GenerateButton`
until `state.chartUploaded`.

**`UploadChartButton.tsx`** — File picker (.csv) → `api.uploadChart` →
dispatch `CHART_UPLOADED` on success; surfaces `invalid_file_type` /
`malformed_csv` / `file_too_large` / `chart_already_exists` inline.

**`UploadEvidenceButton.tsx`** — Small picker for file(s) or a URL text
field → `api.uploadEvidence` per source (repeatable); dispatches
`EVIDENCE_UPLOADED` per successful call; surfaces `url_fetch_failed` etc.
inline. Stays enabled/clickable after use.

**`SystemPromptEditor.tsx`** — Freeform textarea bound to
`systemPromptDraft`; on save calls `api.putSystemPrompt` and dispatches
`SYSTEM_PROMPT_SAVED`. Reused as a modal/drawer when reopened from
`SettingsButton` mid-`WorkspaceScreen`.

**`GenerateButton.tsx`** — Disabled until `chartUploaded`; on click calls
`api.generate`, dispatches `GENERATED` with the opening message, then
calls `api.getChart` to populate `chart.rows`, then sets `screen:
'workspace'`. Surfaces `llm_unavailable` inline with a retry affordance.

**`WorkspaceScreen.tsx`** — Split-pane layout: `ChartPanel` (left),
`ChatPanel` (right).

**`ChartPanel/ChartPanel.tsx`** — Maps `chart.rows` to `ChartRow`.

**`ChartPanel/ChartRow.tsx`** — Renders claim element / evidence /
reasoning / confidence badge; conditionally renders `PendingBanner` (if
`pending_value != null`) or `FlaggedBanner` (if `flagged`, mutually
exclusive with `PendingBanner`); always renders `UndoButton` and
`FlagIcon`. Click (or "Modify") dispatches `ROW_CHIP_STAGED(row.id)`.

**`PendingBanner.tsx`** — Accept/Reject/Modify controls. Accept/Reject
call `api.acceptRow`/`api.rejectRow` directly and re-render that row from
the response; on `409 no_pending_proposal`, silently refetch via
`api.getChart` instead of a toast (stale-UI case, not a user error).
Modify stages the row chip same as clicking the row.

**`FlaggedBanner.tsx`** — Static "Awaiting your description of the issue
in chat" message; no controls of its own.

**`UndoButton.tsx`** — Enabled iff `previous_product_feature != null`;
opens a plain confirm dialog, then calls `api.undoRow`; `409
no_undo_available` handled the same silent-refetch way.

**`FlagIcon.tsx`** — Disabled while `row.flagged`; on click calls
`api.flagRow`, then stages that row's chip in `ChatInput` (same mechanism
as Modify) via `ROW_CHIP_STAGED`.

**`ChatPanel/ChatPanel.tsx`** — Composes `SettingsButton`, `MessageList`,
`ChatInput`, `ExportButton`.

**`SettingsButton.tsx`** — Reopens `SystemPromptEditor` as a modal/drawer
at any point post-Generate.

**`MessageList.tsx`** — Renders `chatMessages` in order; a message with
non-null `row_id` renders an inline `RowChip`.

**`RowChip.tsx`** — Small inline badge (e.g. `@Row[3]`) rendered inside a
message or the input box.

**`ChatInput.tsx`** — Text input; if `pendingRowId` is set, prepends a
non-removable `@Row[n]` chip token. On submit: optimistically appends the
analyst's message to `MessageList`, calls `api.sendChatMessage({content,
row_id: pendingRowId})`, dispatches `MESSAGE_RECEIVED` with the reply, and
if `refresh_chart: true` calls `api.getChart` to pick up the new pending
proposal. Clears `pendingRowId` after submit.

**`ExportButton.tsx`** — Plain link/fetch-blob-and-download against
`api.exportChart`; no state dependency beyond `generated === true`.

## backend/

FastAPI + SQLite. `python-docx` for export, `httpx` + `BeautifulSoup` for
URL evidence fetch.

```
backend/
├── requirements.txt
├── app/
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   ├── db/
│   │   ├── schema.sql
│   │   └── connection.py
│   ├── routers/
│   │   ├── session_router.py
│   │   ├── upload_router.py
│   │   ├── chart_router.py
│   │   ├── chat_router.py
│   │   ├── row_router.py
│   │   ├── system_prompt_router.py
│   │   └── export_router.py
│   ├── services/
│   │   ├── session_service.py
│   │   ├── chart_service.py
│   │   ├── evidence_service.py
│   │   ├── chat_service.py
│   │   └── export_service.py
│   └── ai/
│       ├── provider.py
│       ├── baseline_prompt.py
│       ├── schemas.py
│       ├── validation.py
│       └── features/
│           ├── disambiguation.py
│           ├── refinement_proposal.py
│           ├── initial_classification.py
│           ├── opening_message.py
│           └── regrounded_correction.py
└── tests/
    ├── fakes.py
    ├── test_chart_service.py
    ├── test_csv_parsing.py
    ├── test_export.py
    └── test_url_fetch.py
```

**`main.py`** — FastAPI app instance; mounts all routers under their
prefixes; startup hook reads `LLM_PROVIDER` env var and constructs the
matching `LLMProvider` once (shared across requests).

**`config.py`** — Env-driven settings: `LLM_PROVIDER` (`ollama|openrouter`),
Ollama host/model/`num_ctx`, OpenRouter API key/model route, SQLite file
path, 5MB upload cap constant.

**`errors.py`** — `ApiError` exception type carrying `(status_code, code,
message)`; a FastAPI exception handler renders it as
`{"error": {"code","message"}}`. All routers/services raise this rather
than returning ad-hoc error dicts, keeping the shape consistent (backend-
design §4).

**`db/schema.sql`** — DDL for `sessions`, `rows`, `evidence_docs`,
`chat_messages` exactly as specified in backend-design §2 (including
`rows.flagged` and the `pending_*`/`previous_*` triplets).

**`db/connection.py`** — Opens/holds the SQLite connection (or a
per-request connection factory); helper for running the schema on first
boot if the DB file doesn't exist yet.

**`routers/session_router.py`** — `POST /session`: generates a UUID,
inserts a `sessions` row via `session_service.create_session`, returns
`{session_id}`.

**`routers/upload_router.py`** — `POST /session/{sid}/upload-chart`:
validates extension/size, delegates CSV parsing to
`chart_service.parse_chart_csv`, sets `chart_uploaded=1`.
`POST /session/{sid}/upload-evidence`: validates exactly one of
file/url, delegates `.txt` ingestion or `evidence_service.fetch_url` to
append one `evidence_docs` row.

**`routers/chart_router.py`** — `GET /session/{sid}/chart`: returns all
rows for the session via `chart_service.get_rows`, shaped per
api-contracts.md. `POST /session/{sid}/generate`: calls
`ai.features.initial_classification`, writes `confidence` per row via
`chart_service.apply_classifications`, composes the opening message via
`ai.features.opening_message`, sets `generated=1`.

**`routers/chat_router.py`** — `POST /session/{sid}/chat/message`:
delegates the full resolve→propose orchestration to
`chat_service.handle_message`; returns `{assistant_message,
refresh_chart}`.

**`routers/row_router.py`** — `POST /session/{sid}/rows/{id}/accept` /
`/reject` / `/undo` / `/flag`: each a thin call into the matching
`chart_service` function; `flag` additionally calls
`chat_service.post_flag_system_note`.

**`routers/system_prompt_router.py`** — `GET`/`PUT
/session/{sid}/system-prompt`: reads/writes `sessions.system_prompt` via
`session_service`.

**`routers/export_router.py`** — `GET /session/{sid}/export`: calls
`export_service.build_docx`, streams the binary with the `.docx`
content-type/disposition headers.

**`services/session_service.py`** — `create_session()`,
`get_session(sid)` (raises `session_not_found`), `get_system_prompt(sid)`,
`set_system_prompt(sid, text)`.

**`services/chart_service.py`** — `parse_chart_csv(sid, file_bytes)`
(header-skip, positional column mapping, `malformed_csv`/`file_too_large`
checks), `get_rows(sid)`, `apply_classifications(sid, [{row_id,
confidence}])`, `set_pending(row_id, value, reasoning, confidence)`,
`accept(row_id)` (triplet swap into `previous_*`, clears pending),
`reject(row_id)` (clears pending only), `undo(row_id)` (swaps `previous_*`
back, clears it), `set_flagged(row_id)` / `clear_flagged(row_id)`. Owns
every state-transition rule from backend-design §2's row lifecycle.

**`services/evidence_service.py`** — `store_uploaded_text(sid, filename,
text)`, `fetch_url(url)` (`httpx.get(timeout=10, follow_redirects=True)` →
`BeautifulSoup(...).get_text()`, whitespace-collapsed; raises
`url_fetch_failed` on non-200/timeout/non-HTML), `get_evidence_pool(sid)`
(concatenated content for LLM context and for the verbatim check in
§6.5).

**`services/chat_service.py`** — `handle_message(sid, content, row_id)`:
if `row_id` given, calls `ai.features.refinement_proposal` (or
`regrounded_correction` if that row's `flagged`) directly; if not, calls
`ai.features.disambiguation` first and only chains into the proposal call
within the same request if it resolves. Maps LLM output fields onto
`chart_service.set_pending` per the explicit field-naming translation in
ai-design §4/§6.2, appends both sides of the exchange to `chat_messages`,
returns `{assistant_message, refresh_chart}`. Also
`post_flag_system_note(sid, row_id)` for the `/flag` endpoint's chat note.

**`services/export_service.py`** — `build_docx(sid)`: `python-docx` table
with claim element / evidence / reasoning + confidence badge as
text/color, reading `product_feature` (never `pending_value`) per row.

**`ai/provider.py`** — `LLMProvider` interface: `generate(messages, schema)
-> dict`. `OllamaProvider` (HTTP to `:11434`, passes the JSON Schema as
`format`, sets `num_ctx: 8192`) and `OpenRouterProvider`
(`response_format: json_schema` where supported, else JSON-mode + prompt-
described schema) both implement it. Selected once at startup from
`config.LLM_PROVIDER`; raises a typed `LLMUnavailableError` on
unreachable/timeout, mapped to `502 llm_unavailable` by the routers.

**`ai/baseline_prompt.py`** — The verbatim hidden baseline system-prompt
block from ai-design §5 (rules 1–4), prepended ahead of the analyst's
freeform text and the task instruction on every call. Never returned by
`GET /system-prompt`.

**`ai/schemas.py`** — The JSON Schema for each feature (§6.1's
disambiguation, §6.2/§6.5's shared proposal shape, §6.3's classification
array) as plain dict/JSON-Schema constants; row-id `enum` lists are built
per-request from the session's actual rows, not hardcoded here.

**`ai/validation.py`** — Post-schema checks the schema itself can't
express: the `needs_clarification` ↔ `row_id`/`question` pairing (§6.1),
the `no_evidence_found` ↔ null-fields pairing (§6.2/§6.5), the full-row-set
equality check (§6.3), and the verbatim-substring check against the
evidence pool (§6.5). Each raises a `StructuredOutputError` that callers
retry once (with a correction instruction) before converging on an error/
`no_evidence_found`.

**`ai/features/disambiguation.py`** — `resolve_row(sid, message, history)`:
builds the §6.1 prompt (baseline + freeform + task + chart context + last
~10 messages + new message), calls the provider with the disambiguation
schema, validates, returns `{row_id, needs_clarification, question}`.

**`ai/features/refinement_proposal.py`** — `propose(sid, row_id, message)`:
builds the §6.2 prompt (row data + that row's tagged sub-thread + evidence
pool + message), calls the provider with the shared proposal schema,
validates, returns the raw LLM fields for `chat_service` to map onto
`pending_*`.

**`ai/features/initial_classification.py`** — `classify_all(sid)`: builds
the §6.3 prompt (all rows + evidence pool + the Strong/Moderate/Weak
rubric), calls the provider with the classification-array schema,
validates the full-row-set match, returns `[{row_id, confidence}]`.

**`ai/features/opening_message.py`** — `compose_opening_message(rows)`:
no LLM call — pure template function per §6.4, grouping Weak/Moderate rows
by tier or returning the fixed all-Strong message.

**`ai/features/regrounded_correction.py`** — `correct(sid, row_id,
message)`: same shape as `refinement_proposal.propose` plus the amended
task instruction requiring a verbatim quote; runs the extra verbatim-
substring check from `validation.py` before returning.

**`tests/fakes.py`** — `FakeProvider` implementing `LLMProvider.generate`
with canned per-schema responses (including a malformed-JSON-once mode to
exercise the retry path), so tests never require Ollama/OpenRouter
reachable.

**`tests/test_chart_service.py`** — Accept/reject/undo/flag state
transitions, session step-order enforcement (`chart_not_uploaded`/
`already_generated`).

**`tests/test_csv_parsing.py`** — Header-skip, positional-column-mapping,
`malformed_csv`/`file_too_large` edge cases.

**`tests/test_export.py`** — `.docx` output uses `product_feature` (not
`pending_value`) for pending rows.

**`tests/test_url_fetch.py`** — `evidence_service.fetch_url` error paths
(non-200, timeout, non-HTML).

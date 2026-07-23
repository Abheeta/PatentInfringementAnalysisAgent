# Lumenci Assistant — Backend Design Doc

Derived from `docs/user-flow-steps.md`, `docs/user-flow-diagram.md`, and
`docs/superpowers/specs/2026-07-21-claim-chart-chat-refinement-design.md` (PRD).
This document covers backend and LLM integration for the prototype. See
`docs/superpowers/specs/2026-07-22-frontend-design.md` for the frontend.

## 1. Architecture Overview

```
┌─────────────────┐         HTTP/JSON          ┌──────────────────────┐
│  React Frontend  │ ─────────────────────────▶ │   FastAPI Backend    │
│  (Vite, local)   │ ◀───────────────────────── │   (local, uvicorn)   │
└─────────────────┘                             └──────────┬───────────┘
                                                            │
                        ┌───────────────────────────────────┼───────────────────────┐
                        │                                   │                       │
                 ┌──────▼──────┐                    ┌───────▼───────┐      ┌────────▼────────┐
                 │   SQLite     │                    │  LLM Provider  │      │  URL Fetcher     │
                 │ (sessions,   │                    │  Abstraction   │      │  (httpx + text   │
                 │  rows, undo  │                    │  (interchange- │      │  extraction)     │
                 │  slot,       │                    │  able backend) │      └─────────────────┘
                 │  evidence    │                    └───────┬───────┘
                 │  docs, chat) │                            │
                 └──────────────┘              ┌────────────────┴────────────────┐
                                         ┌──────▼───────┐               ┌────────▼────────┐
                                         │ Ollama (local) │               │  OpenRouter API  │
                                         │ qwen2.5:7b     │               │  qwen-2.5-72b-   │
                                         │ HTTP :11434    │               │  instruct        │
                                         └────────────────┘               └─────────────────┘
```

The backend never talks to Ollama or OpenRouter directly from business logic
— everything goes through one `LLMProvider` interface
(`generate(messages, ...) -> text`) with two implementations selected by an
env var (`LLM_PROVIDER=ollama|openrouter`) at startup. All five LLM-driven
features (classification, opening message, refinement proposals,
disambiguation, re-grounded correction) call this same interface, so
swapping providers or model sizes is a one-line config change with no code
touched elsewhere.

**Sessions:** all state is scoped by a `session_id` (server-generated UUID).
There's no auth — a session isn't a user account, it's just an isolation
boundary so one chart's data never leaks into another. A session is created
explicitly via `POST /session` before any upload happens; the frontend
stores the returned `session_id` and attaches it to every subsequent call.
One session = one chart, start to finish (upload → generate → chat →
export); starting a new chart means creating a new session.

**Deployment target:** local dev only for this prototype — FastAPI + Ollama
+ SQLite all run on the same machine, React served via Vite dev server or a
local static build.

## 2. Backend Design

**Stack:** Python + FastAPI, SQLite, `python-docx` for export, `httpx` +
`BeautifulSoup` for URL evidence fetch.

**Database schema (SQLite)**

See `docs/superpowers/specs/2026-07-22-db-schema.md` for the full `sessions`,
`rows`, `evidence_docs`, and `chat_messages` table definitions and the notes
on how uploaded chart/evidence data maps onto them.

**Upload parsing rules**
- **Header row:** row 1 is always skipped as a header, whatever text it contains; columns are mapped by **position**, not by name (col 1 → `claim_element`, col 2 → `product_feature`, col 3 → `ai_reasoning`). Robust to whatever header wording the analyst's prior process used; a row with a different column count than 3 triggers `malformed_csv`.
- **Encoding:** both the chart CSV and evidence `.txt` files are decoded as `utf-8-sig` (tolerates a BOM); a decode failure returns `malformed_csv` / `invalid_file_type` respectively rather than an unhandled exception.
- **One evidence source per call:** `upload-evidence` accepts exactly one source per call — a single `.txt` file OR a single `{url}` field, never both, never a batch. The endpoint is repeatable, so batching multiple sources means calling it multiple times.
- **File size cap:** 5MB per file (chart CSV and each evidence `.txt`), enforced before parsing; oversized files are rejected with 400 `file_too_large`.
- **Duplicate uploads:** no dedup — re-uploading the same file creates a new `evidence_docs` row each time. Simplest option for a prototype; the only cost is redundant text in the evidence pool.

**Core API endpoints**

All error responses use the shape `{"error": {"code": str, "message": str}}`
(see §4). `session_not_found` (404) applies to every `/session/{sid}/*`
endpoint whenever `sid` doesn't exist, and `row_not_found` (404) applies to
every `/session/{sid}/rows/{id}/*` endpoint whenever `id` doesn't exist —
both are omitted from the per-row table entries below.

The upload/generate flow is three explicit, ordered steps — matching the
frontend's three buttons (upload chart, upload evidence, generate):

| Endpoint | Purpose | Errors / Fallbacks |
|---|---|---|
| `POST /session` | Creates a new session; returns `{session_id}` | — |
| `POST /session/{sid}/upload-chart` | Accepts chart CSV (multipart); parses into `rows` scoped to this session; sets `chart_uploaded=1` | 400 `invalid_file_type` (non-.csv); 400 `malformed_csv` (wrong column count / missing header / decode failure); 400 `file_too_large` (>5MB); 409 `chart_already_exists` if `chart_uploaded` already 1 — no overwrite-on-reupload within a session; start a new session for a new chart |
| `POST /session/{sid}/upload-evidence` | Accepts exactly one evidence source per call — a single `.txt` file OR a single `{url}` (multipart); **repeatable** — each call appends one doc to this session's `evidence_docs` pool | 400 `chart_not_uploaded` if called before `upload-chart` (order enforced); 400 `invalid_file_type` (non-.txt); 400 `file_too_large` (>5MB); 400 `invalid_request` (neither/both of file/url provided); URL fetch errors — see §4 |
| `POST /session/{sid}/generate` | Triggers the initial LLM classification pass over all rows + the evidence pool, sets each row's `confidence`, seeds the opening chat message; sets `generated=1` | 400 `chart_not_uploaded`; 409 `already_generated` if `generated` already 1 — evidence is optional at this point, rows with none simply classify Weak; 502 `llm_unavailable` if the provider call fails after retry |
| `GET /session/{sid}/chart` | Returns current rows incl. pending state, confidence tiers | 400 `chart_not_uploaded` if nothing uploaded yet |
| `POST /session/{sid}/chat/message` | Analyst message (+ optional row_id from `@Row` chip) → orchestrates resolve→propose flow, returns AI reply + any new pending proposal | 400 `not_generated_yet` if `/generate` hasn't run; 400 `empty_message`; 502 `llm_unavailable` if the provider call fails after retry; 404 `row_not_found` if `row_id` is explicitly provided and invalid — not covered by the blanket note above, since `row_id` here is a body field, not a `/rows/{id}/*` path segment |
| `POST /session/{sid}/rows/{id}/accept` | Copies current `(product_feature, ai_reasoning, confidence)` into `previous_*` (the undo slot), then commits `(pending_value, pending_reasoning, pending_confidence)` → `(product_feature, ai_reasoning, confidence)` as one atomic triplet; clears all `pending_*` | 409 `no_pending_proposal` if `pending_value` is NULL |
| `POST /session/{sid}/rows/{id}/reject` | Clears pending, no DB value change | 409 `no_pending_proposal` if `pending_value` is NULL |
| `POST /session/{sid}/rows/{id}/undo` | Swaps `(product_feature, ai_reasoning, confidence)` ↔ `(previous_*)` as one atomic triplet, then clears `previous_*` (single-step: nothing left to re-undo); the confirm dialog is UI-only, so this call carries no confirmation field | 409 `no_undo_available` if `previous_product_feature` is NULL |
| `POST /session/{sid}/rows/{id}/flag` | Sets `rows.flagged=1` for re-grounded correction and posts an `@Row`-anchored system note into chat prompting the analyst to describe the issue; the analyst's next chat message is what drives the actual re-scan/correction (see ai-design doc), and clears `flagged` back to 0 once that call returns | 404 `no_evidence_pool` if this session's `evidence_docs` is empty (nothing to re-scan); 409 `already_flagged` if `flagged` is already 1 (mid re-scan, awaiting the analyst's description) |
| `GET /session/{sid}/system-prompt` / `PUT /session/{sid}/system-prompt` | Read/update the analyst's freeform text (baseline is never exposed) | — |
| `GET /session/{sid}/export` | Streams generated `.docx` | 400 `not_generated_yet` |

Row-mutation endpoints (`accept`/`reject`/`undo`) are the "double-click /
stale UI" case: on a 409, the frontend simply refreshes that row from
`GET /session/{sid}/chart` rather than surfacing a user-facing error toast,
since the UI already disables these controls when there's nothing to act
on — a 409 means the client was out of sync, not a real user error.

**Chat message handling (high level):** an analyst message either resolves
to a specific row (via `row_id` or AI inference) and produces a proposal,
a clarifying question, or a "no evidence found" reply — or it doesn't
resolve confidently, in which case the AI asks which row is meant rather
than guessing. Every accepted resolution is grounded in this session's
evidence pool; nothing is written to a row's live values until the analyst
explicitly accepts. Full prompt/context/orchestration design is in the
ai-design doc.

**Flag flow (high level):** flagging a row is a deterministic trigger that
opens a re-grounded-correction conversation for that row — the analyst
describes what's wrong, and the AI's correction must quote evidence
verbatim from this session's pool or report none was found, same as any
other proposal. Full flow detail is in the ai-design doc.

**Export** — `export_service` builds the `.docx` via `python-docx`: a table
with the same 3 columns + confidence badge as text/color, reading
`product_feature` (not `pending_value`) for every row, per the PRD's
"pending exports as current unaccepted value" rule.

## 3. LLM Design

See `docs/superpowers/specs/<TBD>-ai-design.md` for LLM provider abstraction,
prompt design, structured-output handling, and context/chat management —
being rebuilt from scratch to ensure consistency with the API contracts.

## 4. Evidence Fetch, Error Handling & Testing

**URL fetch/extraction** (`evidence_service.fetch_url`)
- `httpx.get(url, timeout=10, follow_redirects=True)` — single page, no crawling.
- HTML → text via `BeautifulSoup(html, "html.parser").get_text()`, whitespace-collapsed.
- Stored as a new `evidence_docs` row (`source_type='url'`) scoped to the session, then fed into the pending refinement proposal exactly like an uploaded doc.
- Failure modes handled explicitly: non-200 status, timeout, non-HTML content-type — each returns a clear chat message ("Couldn't fetch that URL: <reason>. Try another URL or upload a document instead.") rather than a raw exception surfacing to the frontend.

**Error handling conventions**
- All routers return a consistent error shape `{"error": {"code": str, "message": str}}` with appropriate HTTP status; frontend shows these inline in chat or as a small toast, never a blank crash.
- LLM call failures (provider unreachable, timeout) are caught in `llm/provider.py` and surfaced as a chat-visible error ("The AI is temporarily unavailable, please retry") rather than a 500 bubbling to a blank screen — this matters especially for the Ollama path, which can fail if the local model isn't pulled/running.
- JSON-mode parse failures: retried once with a correction instruction (see ai-design doc); if that also fails, treat as a backend error surfaced in chat rather than silently guessing at malformed output.
- Upload validation: reject non-.csv files and malformed CSVs (wrong column count) with a specific message before any LLM call is attempted, per the acceptance criterion that empty/no-upload state never crashes.

**Testing strategy** (matches "prototype" scope — no exhaustive test pyramid)
- **Backend unit tests (pytest):** `chart_service` transitions (accept/reject/undo/flag state changes), CSV parsing edge cases, `.docx` export producing the right column values from `product_feature` vs `pending_value`, URL-fetch error handling, session step-order enforcement (`chart_not_uploaded`/`already_generated`) — all with the LLM provider mocked (a `FakeProvider` returning canned JSON) so tests don't depend on Ollama/OpenRouter being reachable.
- **Prompt/JSON-contract tests:** feed the `FakeProvider` malformed JSON once to verify the retry-then-error path actually fires.
- **Manual/integration pass:** one real end-to-end run against both providers (Ollama local, then OpenRouter) before demo, checking the five LLM-driven features produce sane output — this is the one place where using both providers actually gets exercised as intended.

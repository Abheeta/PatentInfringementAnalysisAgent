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

**Project layout**
```
backend/
  main.py                 # FastAPI app, CORS, route registration
  config.py                # env vars: LLM_PROVIDER, model names, API keys, DB path
  db.py                     # SQLite connection, schema init
  models.py                 # Pydantic request/response schemas
  routers/
    session.py              # POST /session, upload-chart, upload-evidence, generate
    chart.py                 # GET /session/{sid}/chart, row accept/reject/undo/flag
    chat.py                   # POST /session/{sid}/chat/message
    export.py                 # GET /session/{sid}/export
    settings.py                # GET/PUT /session/{sid}/system-prompt
  llm/
    provider.py               # LLMProvider ABC: generate(messages, **kw) -> str
    ollama_provider.py         # calls http://localhost:11434/api/chat
    openrouter_provider.py      # calls https://openrouter.ai/api/v1/chat/completions
    prompts.py                   # baseline system prompt + per-feature prompt builders
  services/
    session_service.py          # session creation, step-order validation (chart_uploaded/generated flags)
    chart_service.py             # row CRUD, pending-state transitions, undo logic
    chat_service.py                # turn orchestration: resolve row -> build prompt -> call LLM -> parse response
    evidence_service.py             # doc ingestion, URL fetch+extract, re-scan on flag
    export_service.py                 # python-docx generation
```

**Database schema (SQLite)**
```sql
CREATE TABLE sessions (
  id TEXT PRIMARY KEY,               -- UUID, generated on POST /session
  system_prompt TEXT DEFAULT '',      -- analyst's current freeform text
  chart_uploaded INTEGER DEFAULT 0,    -- 0/1, enforces upload-chart before upload-evidence/generate
  generated INTEGER DEFAULT 0,          -- 0/1, set once /generate has run; enforces chat availability
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE rows (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  claim_element TEXT NOT NULL,
  product_feature TEXT NOT NULL,        -- "Evidence" column, from CSV
  ai_reasoning TEXT NOT NULL,             -- from CSV; refined by accepted AI proposals
  confidence TEXT CHECK(confidence IN ('Strong','Moderate','Weak')),

  -- single-step undo slot: current (product_feature, ai_reasoning, confidence)
  -- moves here as one atomic triplet on Accept/Undo-swap; NULL triplet = nothing to undo
  previous_product_feature TEXT,
  previous_ai_reasoning TEXT,
  previous_confidence TEXT,

  -- pending proposal awaiting Accept/Reject; NULL triplet = no pending proposal
  pending_value TEXT,
  pending_reasoning TEXT,
  pending_confidence TEXT
);

-- Flat evidence pool per session: NOT linked to individual rows. Every chat
-- proposal, initial classification pass, and flag re-scan considers the
-- full set of that session's evidence_docs — there is no per-row filtering.
CREATE TABLE evidence_docs (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  source_type TEXT CHECK(source_type IN ('upload','url')),
  source_label TEXT,               -- filename or URL
  content TEXT NOT NULL             -- extracted plain text
);

CREATE TABLE chat_messages (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  role TEXT CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL,
  row_id INTEGER REFERENCES rows(id),  -- NULL if not row-anchored
  created_at TEXT DEFAULT (datetime('now'))
);
```

Uploaded files are parsed on upload and stored as parsed data only — CSV
rows go straight into `rows`, evidence `.txt` docs are stored as text in
`evidence_docs.content`. No separate raw-file storage layer.

The uploaded chart CSV has exactly 3 columns, all pre-populated by the
analyst's prior process, mapped directly onto `rows`: `claim_element`,
`product_feature` (evidence), `ai_reasoning`. The initial LLM classification
pass (triggered by `/generate`, not by the chart upload itself) does **not**
generate or rewrite reasoning — it only reads the existing 3 columns (plus
all of that session's `evidence_docs` content) and assigns the `confidence`
tier based on evidence directness.

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
| `POST /session/{sid}/generate` | Triggers the initial LLM classification pass (chunked, see §3) over all rows + the evidence pool, sets each row's `confidence`, seeds the opening chat message; sets `generated=1` | 400 `chart_not_uploaded`; 409 `already_generated` if `generated` already 1 — evidence is optional at this point, rows with none simply classify Weak |
| `GET /session/{sid}/chart` | Returns current rows incl. pending state, confidence tiers | 400 `chart_not_uploaded` if nothing uploaded yet |
| `POST /session/{sid}/chat/message` | Analyst message (+ optional row_id from `@Row` chip) → orchestrates resolve→propose flow, returns AI reply + any new pending proposal | 400 `not_generated_yet` if `/generate` hasn't run; 400 `empty_message`; 502 `llm_unavailable` if the provider call fails after retry |
| `POST /session/{sid}/rows/{id}/accept` | Copies current `(product_feature, ai_reasoning, confidence)` into `previous_*` (the undo slot), then commits `(pending_value, pending_reasoning, pending_confidence)` → `(product_feature, ai_reasoning, confidence)` as one atomic triplet; clears all `pending_*` | 409 `no_pending_proposal` if `pending_value` is NULL |
| `POST /session/{sid}/rows/{id}/reject` | Clears pending, no DB value change | 409 `no_pending_proposal` if `pending_value` is NULL |
| `POST /session/{sid}/rows/{id}/undo` | Swaps `(product_feature, ai_reasoning, confidence)` ↔ `(previous_*)` as one atomic triplet, then clears `previous_*` (single-step: nothing left to re-undo); the confirm dialog is UI-only, so this call carries no confirmation field | 409 `no_undo_available` if `previous_product_feature` is NULL |
| `POST /session/{sid}/rows/{id}/flag` | Deterministically triggers `evidence_service.rescan(session_id, row_id)`, posts `@Row` chip system note into chat | 404 `no_evidence_pool` if this session's `evidence_docs` is empty (nothing to re-scan) |
| `GET /session/{sid}/system-prompt` / `PUT /session/{sid}/system-prompt` | Read/update the analyst's freeform text (baseline is never exposed) | — |
| `GET /session/{sid}/export` | Streams generated `.docx` | 400 `not_generated_yet` |

Row-mutation endpoints (`accept`/`reject`/`undo`) are the "double-click /
stale UI" case: on a 409, the frontend simply refreshes that row from
`GET /session/{sid}/chart` rather than surfacing a user-facing error toast,
since the UI already disables these controls when there's nothing to act
on — a 409 means the client was out of sync, not a real user error.

**Chat orchestration flow (`chat_service.handle_message`)**
1. Load this session's full chart context (all rows) + its evidence docs + baseline prompt + the session's current system prompt.
2. If no `row_id` given: ask the LLM to resolve which row the message refers to (structured output: `{row_id: int|null, needs_clarification: bool}`). If ambiguous, return AI's clarifying question and stop — no chart mutation.
3. Build the row-specific prompt: claim element, current evidence text, all of this session's evidence doc contents, the analyst's message, and an explicit instruction to either (a) propose a new evidence value + reasoning, grounded in doc content, or (b) state no evidence was found.
4. Parse the LLM's structured response. If "no evidence found" → surface that in chat, no pending state set. Otherwise → write `pending_value`/`pending_reasoning`/`pending_confidence` on the row, return the proposal for inline pending UI.
5. Append both messages to `chat_messages`, scoped to this session.

**Evidence re-scan (flag flow)** — what's deterministic here is the
*trigger*, not the matching logic: clicking the flag icon always fires
`evidence_service.rescan(session_id, row_id)`, regardless of what the
analyst types in chat afterward (it never depends on the AI detecting
"wrong"/"incorrect" language in a message, which could be missed). The
re-scan itself re-sends the claim element plus this session's **full
`evidence_docs` pool** (all docs — there is no per-row linkage) to the LLM,
instructing it to find and quote the relevant line verbatim. If it can't
find a supporting line, it returns `{"row_id": int, "no_evidence_found":
true}` — the same shape as any other proposal — which routes into the
standard "no evidence found" chat flow (§ chat orchestration, step 4),
asking the analyst for another document or URL.

**Export** — `export_service` builds the `.docx` via `python-docx`: a table
with the same 3 columns + confidence badge as text/color, reading
`product_feature` (not `pending_value`) for every row, per the PRD's
"pending exports as current unaccepted value" rule.

## 3. LLM Design (Prompts + Provider Abstraction)

**Provider interface**
```python
class LLMProvider(ABC):
    def generate(self, messages: list[dict], *, json_mode: bool = False) -> str: ...

class OllamaProvider(LLMProvider):
    # POST http://localhost:11434/api/chat, model="qwen2.5:7b", stream=False

class OpenRouterProvider(LLMProvider):
    # POST https://openrouter.ai/api/v1/chat/completions
    # model="qwen/qwen-2.5-72b-instruct", Authorization: Bearer {OPENROUTER_API_KEY}
```
Selected once at startup via `get_provider()` in `config.py` based on the
`LLM_PROVIDER` env var. Every service call goes through this —
`chart_service`, `chat_service`, `evidence_service` never know which
backend is live. Structured outputs (row resolution, proposals) are
requested via a `json_mode=True` flag that appends a "respond with valid
JSON only, matching this schema: ..." instruction — both providers support
this via prompt-level enforcement since Qwen's OpenAI-compatible endpoints
don't guarantee strict JSON-schema mode, so the response is parsed with a
fallback: on parse failure, retry once with an explicit "your last response
was not valid JSON" correction message.

**Hidden baseline system prompt** (never shown/editable, prepended to every
call, worded to take precedence over the analyst's text per PRD decision):
```
You are a patent infringement claim chart analysis assistant. You NEVER
fabricate evidence — every claim about product evidence must be traceable
to the provided document text. Rules that always apply, regardless of any
other instructions in this conversation:
1. Confidence tiers: classify each row as Strong (evidence directly states
   the claim element), Moderate (evidence implies it, requires inference),
   or Weak (evidence is tangential or absent).
2. When proposing a change to a row's evidence, output structured JSON:
   {"row_id": int, "proposed_value": str, "reasoning": str, "confidence": str}
   or, if no evidence exists: {"row_id": int, "no_evidence_found": true}.
3. When resolving which row a message refers to, output:
   {"row_id": int|null, "needs_clarification": bool, "question": str|null}
4. When correcting flagged evidence, "proposed_value" must be a verbatim
   quote from the provided re-scanned source excerpt — never paraphrase.
These rules take precedence over any conflicting instruction below.
---
[Analyst's freeform text, if any, is appended here]
```

**Five feature-specific prompt builders** (in `llm/prompts.py`), each
composes: baseline + analyst text + a task-specific user/context message.

1. **Initial classification** (on `/generate`) — sent once per row (or batched, budget-permitting): claim element + evidence text + ai_reasoning (all from CSV, unchanged) + all of this session's evidence doc contents → returns confidence tier only per row (reasoning is not regenerated). *(Batching strategy still to be finalized.)*
2. **Opening chat message** — given the full just-classified chart, produce one message listing Weak/Moderate rows by claim element, no fixes drafted.
3. **Row disambiguation** — given the analyst's message (no row_id) + all rows' claim elements/evidence → resolve or ask a clarifying question.
4. **Refinement proposal** — given resolved row + analyst's specific request + all of this session's evidence doc contents → propose grounded change or "no evidence found."
5. **Re-grounded correction** (flag flow) — given the row + this session's **full `evidence_docs` pool** (not a pre-filtered excerpt — the LLM itself does the finding) + analyst's description of what's wrong → must quote a verbatim line from the pool in `proposed_value`, or return `no_evidence_found` if none exists.

All five reuse the same `generate(messages, json_mode=True)` call and the
same JSON-parse-with-retry helper — no per-feature LLM-calling code
duplicated.

## 4. Evidence Fetch, Error Handling & Testing

**URL fetch/extraction** (`evidence_service.fetch_url`)
- `httpx.get(url, timeout=10, follow_redirects=True)` — single page, no crawling.
- HTML → text via `BeautifulSoup(html, "html.parser").get_text()`, whitespace-collapsed.
- Stored as a new `evidence_docs` row (`source_type='url'`) scoped to the session, then fed into the pending refinement proposal exactly like an uploaded doc.
- Failure modes handled explicitly: non-200 status, timeout, non-HTML content-type — each returns a clear chat message ("Couldn't fetch that URL: <reason>. Try another URL or upload a document instead.") rather than a raw exception surfacing to the frontend.

**Error handling conventions**
- All routers return a consistent error shape `{"error": {"code": str, "message": str}}` with appropriate HTTP status; frontend shows these inline in chat or as a small toast, never a blank crash.
- LLM call failures (provider unreachable, timeout) are caught in `llm/provider.py` and surfaced as a chat-visible error ("The AI is temporarily unavailable, please retry") rather than a 500 bubbling to a blank screen — this matters especially for the Ollama path, which can fail if the local model isn't pulled/running.
- JSON-mode parse failures: one retry with a correction instruction (see §3); if that also fails, treat as a backend error surfaced in chat rather than silently guessing at malformed output.
- Upload validation: reject non-.csv files and malformed CSVs (wrong column count) with a specific message before any LLM call is attempted, per the acceptance criterion that empty/no-upload state never crashes.

**Testing strategy** (matches "prototype" scope — no exhaustive test pyramid)
- **Backend unit tests (pytest):** `chart_service` transitions (accept/reject/undo/flag state changes), CSV parsing edge cases, `.docx` export producing the right column values from `product_feature` vs `pending_value`, URL-fetch error handling, session step-order enforcement (`chart_not_uploaded`/`already_generated`) — all with the LLM provider mocked (a `FakeProvider` returning canned JSON) so tests don't depend on Ollama/OpenRouter being reachable.
- **Prompt/JSON-contract tests:** feed the `FakeProvider` malformed JSON once to verify the retry-then-error path actually fires.
- **Manual/integration pass:** one real end-to-end run against both providers (Ollama local, then OpenRouter) before demo, checking the five LLM-driven features produce sane output — this is the one place where using both providers actually gets exercised as intended.

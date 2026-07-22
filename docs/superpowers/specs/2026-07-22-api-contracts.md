# Lumenci Assistant — API Contracts

Request/response JSON for each endpoint, built up one at a time. Companion
to `docs/superpowers/specs/2026-07-22-backend-design.md` (§2 has the
endpoint purpose/error-code table this doc fills in with exact payloads).
Shared object shapes (`Row`, `ChatMessage`, error envelope) are TBD — for
now each endpoint's examples are shown standalone.

### `POST /session`

Creates a new session. First call the frontend makes on app load when no
`session_id` is in `localStorage`.

**Request** — empty body, no fields.

**Response — `201 Created`**
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

| Field | Type | Notes |
|---|---|---|
| `session_id` | string (UUID v4) | Generated server-side. Frontend stores this and attaches it as `{sid}` on every subsequent call. |

**Errors:** none — pure UUID generation + row insert, no failure modes.

### `POST /session/{sid}/upload-chart`

Accepts the chart CSV, parses it into `rows` scoped to this session, sets
`chart_uploaded=1`.

**Request** — `multipart/form-data`, one field:

| Field | Type | Notes |
|---|---|---|
| `file` | file (.csv) | 3-column CSV, header row always skipped, columns mapped by position. Max 5MB. |

**Response — `204 No Content`** — empty body. On success the frontend
dispatches `CHART_UPLOADED` and, if it needs the parsed rows for a preview,
follows up with `GET /session/{sid}/chart`.

**Errors**
```json
// 400 invalid_file_type
{"error": {"code": "invalid_file_type", "message": "Only .csv files are accepted."}}

// 400 malformed_csv
{"error": {"code": "malformed_csv", "message": "Row 4 has 2 columns, expected 3."}}

// 400 file_too_large
{"error": {"code": "file_too_large", "message": "File exceeds the 5MB limit."}}

// 409 chart_already_exists
{"error": {"code": "chart_already_exists", "message": "A chart has already been uploaded for this session. Start a new session to upload a different chart."}}

// 404 session_not_found (applies to all /session/{sid}/* endpoints)
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/upload-evidence`

Accepts one evidence source per call — a `.txt` file or a URL — and appends
it to this session's `evidence_docs` pool. Repeatable: call again to add
more sources in additional batches before (or after) `/generate`.

**Request** — `multipart/form-data`, exactly one of:

| Field | Type | Notes |
|---|---|---|
| `file` | file (.txt) | Single `.txt` file. Max 5MB. |
| `url` | string | Single URL, fetched server-side (single page, no crawl/JS). |

**Response — `204 No Content`** — empty body. On success the frontend
dispatches `EVIDENCE_UPLOADED`; no chart re-render is needed since evidence
isn't shown in the chart panel.

**Errors**
```json
// 400 chart_not_uploaded
{"error": {"code": "chart_not_uploaded", "message": "Upload a chart before adding evidence."}}

// 400 invalid_file_type
{"error": {"code": "invalid_file_type", "message": "Only .txt files are accepted."}}

// 400 file_too_large
{"error": {"code": "file_too_large", "message": "'product_spec.txt' exceeds the 5MB limit."}}

// 400 invalid_request (neither or both of file/url provided)
{"error": {"code": "invalid_request", "message": "Provide exactly one of file or url."}}

// 400 url_fetch_failed (covers non-200, timeout, non-HTML content-type)
{"error": {"code": "url_fetch_failed", "message": "Couldn't fetch that URL: request timed out after 10s."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `GET /session/{sid}/chart`

Returns the current state of every row, including pending proposals and
undo availability. This is the single source of truth for chart state —
the frontend calls it to refresh after every mutating action (`/generate`,
`upload-chart`, accept/reject/undo), rather than those endpoints each
returning their own copy of row data. This is the canonical `Row` shape
referenced elsewhere in this doc.

**Request** — no body, no query params.

**Response — `200 OK`**
```json
{
  "rows": [
    {
      "id": 1,
      "claim_element": "a processor configured to receive a signal",
      "product_feature": "The device includes a Snapdragon processor...",
      "ai_reasoning": "Product spec sheet describes signal reception via the modem chip.",
      "confidence": "Strong",
      "pending_value": null,
      "pending_reasoning": null,
      "pending_confidence": null,
      "previous_product_feature": null,
      "previous_ai_reasoning": null,
      "previous_confidence": null
    },
    {
      "id": 3,
      "claim_element": "a memory storing instructions",
      "product_feature": "No mention of onboard memory found in current sources.",
      "ai_reasoning": "No supporting evidence located.",
      "confidence": "Weak",
      "pending_value": "The device ships with 8GB LPDDR5 onboard memory per the teardown report.",
      "pending_reasoning": "Teardown report explicitly lists memory spec.",
      "pending_confidence": "Strong",
      "previous_product_feature": null,
      "previous_ai_reasoning": null,
      "previous_confidence": null
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `pending_*` | string \| null | Non-null when a proposal is awaiting Accept/Reject (row 3 above). |
| `previous_*` | string \| null | Non-null when an accepted change can still be undone. |

**Errors**
```json
// 400 chart_not_uploaded
{"error": {"code": "chart_not_uploaded", "message": "Upload a chart before viewing it."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/generate`

Runs the initial LLM classification pass over all rows + the evidence
pool, sets each row's `confidence`, seeds the opening chat message, sets
`generated=1`.

**Request** — empty body, no fields.

**Response — `200 OK`**
```json
{
  "generated": true,
  "opening_message": {
    "id": 1,
    "role": "assistant",
    "content": "I've reviewed the chart. Rows 3 and 7 are Weak, row 5 is Moderate — let me know if you'd like to work through them.",
    "row_id": null,
    "created_at": "2026-07-22T10:15:00Z"
  }
}
```
No `rows` here — `GET /session/{sid}/chart` is the single source of truth
for chart state and is called to refresh it at every point (including
right after `/generate`), so this response only carries what `GET /chart`
doesn't have: the `generated` flag flip and the opening chat message.

**Errors**
```json
// 400 chart_not_uploaded
{"error": {"code": "chart_not_uploaded", "message": "Upload a chart before generating."}}

// 409 already_generated
{"error": {"code": "already_generated", "message": "This session has already been generated."}}

// 502 llm_unavailable
{"error": {"code": "llm_unavailable", "message": "The AI is temporarily unavailable, please retry."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/chat/message`

Analyst sends a chat message, optionally anchored to a row via the `@Row`
chip. Orchestrates resolve → propose and returns the AI's reply as chat
messages; any resulting pending state is picked up via `GET /chart`.

**Request**
```json
{
  "content": "This looks weak, can you check the teardown report for memory specs?",
  "row_id": 3
}
```

| Field | Type | Notes |
|---|---|---|
| `content` | string | The analyst's message text. Required, non-empty. |
| `row_id` | int \| null | Present if sent via a row click / Modify / Flag chip. `null` if typed freely — the AI resolves the row itself. |

**Response — `200 OK`** — same shape regardless of what the AI does
(proposal made / clarification asked / no evidence found); only
`assistant_message.content` and `refresh_chart` differ. The analyst's own
message isn't echoed back — the frontend already has it (it's what was
just submitted) and appends it to `MessageList` optimistically on send.

| Field | Type | Notes |
|---|---|---|
| `assistant_message` | ChatMessage | The AI's reply. |
| `refresh_chart` | boolean | `true` iff this turn set a pending proposal on a row — tells the frontend to call `GET /session/{sid}/chart` to pick it up. `false` for clarification questions and "no evidence found" replies, since neither changes row state. |

Row resolved, proposal made:
```json
{
  "assistant_message": {"id": 21, "role": "assistant", "content": "Found it — the teardown report lists 8GB LPDDR5 onboard memory. Proposing an update to row 3.", "row_id": 3, "created_at": "2026-07-22T10:20:03Z"},
  "refresh_chart": true
}
```

Ambiguous row reference — AI asks for clarification, no mutation:
```json
{
  "assistant_message": {"id": 21, "role": "assistant", "content": "Which row did you mean — row 3 (memory) or row 5 (signal processing)?", "row_id": null, "created_at": "2026-07-22T10:20:02Z"},
  "refresh_chart": false
}
```

No evidence found:
```json
{
  "assistant_message": {"id": 21, "role": "assistant", "content": "I couldn't find supporting evidence for row 3 in the uploaded docs. Can you upload another document or provide a URL?", "row_id": 3, "created_at": "2026-07-22T10:20:03Z"},
  "refresh_chart": false
}
```

**Errors**
```json
// 400 not_generated_yet
{"error": {"code": "not_generated_yet", "message": "Run Generate before chatting."}}

// 400 empty_message
{"error": {"code": "empty_message", "message": "Message content cannot be empty."}}

// 502 llm_unavailable
{"error": {"code": "llm_unavailable", "message": "The AI is temporarily unavailable, please retry."}}

// 404 row_not_found (only when row_id is explicitly provided and invalid)
{"error": {"code": "row_not_found", "message": "Row 99 not found in this session."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/rows/{id}/accept`

Commits the pending proposal: current values move to the undo slot, the
pending triplet becomes the row's live values, pending state clears.

**Request** — empty body, no fields.

**Response — `204 No Content`** — empty body. Frontend refreshes the
affected row (or the whole chart) via `GET /session/{sid}/chart`.

**Errors**
```json
// 409 no_pending_proposal
{"error": {"code": "no_pending_proposal", "message": "Row 3 has no pending proposal to accept."}}

// 404 row_not_found
{"error": {"code": "row_not_found", "message": "Row 3 not found in this session."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/rows/{id}/reject`

Clears the pending proposal. No change to the row's live values or undo
slot.

**Request** — empty body, no fields.

**Response — `204 No Content`** — empty body. Frontend refreshes the
affected row (or the whole chart) via `GET /session/{sid}/chart`.

**Errors**
```json
// 409 no_pending_proposal
{"error": {"code": "no_pending_proposal", "message": "Row 3 has no pending proposal to reject."}}

// 404 row_not_found
{"error": {"code": "row_not_found", "message": "Row 3 not found in this session."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/rows/{id}/undo`

Reverts the row to its previous (pre-accept) values and clears the undo
slot. The confirm dialog is a UI-only step — by the time this call fires,
confirmation has already happened client-side, so the request carries no
confirmation field.

**Request** — empty body, no fields.

**Response — `204 No Content`** — empty body. Frontend refreshes the
affected row (or the whole chart) via `GET /session/{sid}/chart`.

**Errors**
```json
// 409 no_undo_available
{"error": {"code": "no_undo_available", "message": "Row 3 has no previous value to undo to."}}

// 404 row_not_found
{"error": {"code": "row_not_found", "message": "Row 3 not found in this session."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `POST /session/{sid}/rows/{id}/flag`

Deterministically triggers a re-scan of the session's evidence pool for
this row's claim element, and posts a system note into chat prompting the
analyst to describe what's wrong. The analyst's next chat message (with
this row's `@Row` chip attached) is what actually drives the re-grounded
correction — see `/chat/message` — this endpoint just marks the row and
opens the conversation.

**Request** — empty body, no fields.

**Response — `200 OK`**
```json
{
  "system_note": {
    "id": 22,
    "role": "assistant",
    "content": "Row 3 flagged for re-scan. What's wrong with the current evidence?",
    "row_id": 3,
    "created_at": "2026-07-22T10:25:00Z"
  }
}
```

**Errors**
```json
// 404 no_evidence_pool
{"error": {"code": "no_evidence_pool", "message": "No evidence has been uploaded for this session yet — nothing to re-scan."}}

// 404 row_not_found
{"error": {"code": "row_not_found", "message": "Row 3 not found in this session."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `GET /session/{sid}/system-prompt`

Returns the analyst's current freeform system-prompt text (the hidden
baseline prompt is never exposed).

**Request** — no body.

**Response — `200 OK`**
```json
{"system_prompt": "Be conservative — only mark Strong if the evidence uses near-identical wording to the claim element."}
```

**Errors**
```json
// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `PUT /session/{sid}/system-prompt`

Overwrites the analyst's freeform system-prompt text.

**Request**
```json
{"system_prompt": "Be conservative — only mark Strong if the evidence uses near-identical wording to the claim element."}
```

**Response — `204 No Content`** — empty body. Frontend already has the
text it just submitted (it's what's in `SystemPromptEditor`), so nothing
needs echoing back.

**Errors**
```json
// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

### `GET /session/{sid}/export`

Streams the current chart state as a generated `.docx`. Always available
once `/generate` has run — pending (unaccepted) cells export using their
current `product_feature` value, per the PRD.

**Request** — no body.

**Response — `200 OK`**
- `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `Content-Disposition: attachment; filename="claim_chart.docx"`
- Body: binary `.docx` stream (no JSON envelope).

**Errors**
```json
// 400 not_generated_yet
{"error": {"code": "not_generated_yet", "message": "Run Generate before exporting."}}

// 404 session_not_found
{"error": {"code": "session_not_found", "message": "Session '3fa85f64-...' not found."}}
```

# Single Active Flag — Design

Restricts flagging to one row at a time per session. While a row is
flagged (awaiting the analyst's description of the issue in chat), no
other row can be flagged, in both the frontend and the backend.

## Backend

`chart_service.set_flagged(sid, row_id)` currently only checks whether
the *target* row is already flagged. It's extended to check whether
*any* row in the session is flagged:

- Query: `SELECT id FROM rows WHERE session_id = ? AND flagged = 1`.
- If the flagged row is the same as `row_id`: raise the existing
  `already_flagged` (409) with the existing message —
  `"Row {row_id} is already awaiting your description of the issue."`
- If the flagged row is a *different* row: raise `already_flagged`
  (409, same error code — reused rather than introducing a new one)
  with a message naming the blocking row —
  `"Row {blocking_id} is already awaiting your description of the issue — resolve it before flagging another row."`

No schema change, no new endpoint. `row_router.flag_row` is unchanged
— the branching lives entirely in `chart_service.set_flagged`.

## Frontend

`FlagIcon` currently disables its button only when `row.flagged` is
true, with a static "Flag for re-scan" tooltip.

- Reads `chart.rows` from `useSessionState()` to determine if any
  *other* row (`r.id !== row.id`) has `flagged === true`.
- Button `disabled` becomes: `row.flagged || Boolean(blockingRow)`.
- Tooltip becomes conditional:
  - Own row flagged (existing case): unchanged — "Flag for re-scan"
    button is disabled because there's nothing to (re-)flag until it
    resolves.
  - Blocked by another row: `"Resolve the flag on row {blockingRow.id} first"`.
  - Neither: existing "Flag for re-scan".
- `handleFlag`'s existing early-return guard (`if (!sessionId ||
  row.flagged) return;`) stays as defense in depth, extended to also
  return early when blocked by another row. If a stale render lets a
  blocked click through anyway and the backend rejects it with
  `already_flagged`, `FlagIcon` follows the same local-error pattern
  used by `UploadChartButton`/`GenerateButton`/`ChatInput`: a
  `const [error, setError] = useState<string | null>(null)` set in the
  `catch` block to `err instanceof ApiError ? err.message : "Flag failed."`,
  rendered as an inline `<p role="alert">` positioned near the icon.

No new API contract fields — `GET /session/{sid}/chart`'s existing
per-row `flagged` boolean is sufficient for the frontend to compute
this client-side; no new endpoint or response field is needed.

## Out of scope

- No change to how a flag is *cleared* (`clear_flagged`, driven by the
  chat re-grounded-correction flow) — that path is untouched.
- No session-level `flagged` summary field on `GET /chart` — the
  frontend derives "is anything flagged" by scanning `rows`.

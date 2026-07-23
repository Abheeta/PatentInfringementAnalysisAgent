# Single Active Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent flagging more than one row at a time per session — both the backend API and the frontend UI must block a second flag while one is still unresolved, with a clear message naming the blocking row.

**Architecture:** Backend gains a session-wide check in `chart_service.set_flagged` (query for any row with `flagged=1` in the session, not just the target row) that reuses the existing `already_flagged` (409) error code with a message naming the blocking row. Frontend's `FlagIcon` derives "is another row flagged" from the `chart.rows` array already in `SessionContext` state — no new API field needed — and disables the button with a tooltip naming the blocking row.

**Tech Stack:** FastAPI + sqlite3 (backend), pytest + `TestClient` (backend tests), React + TypeScript + Vite (frontend), no frontend test framework installed (manual/browser verification only).

## Global Constraints

- Reuse the existing `already_flagged` error code for both the same-row and different-row cases (no new error code) — per `docs/superpowers/specs/2026-07-23-single-active-flag-design.md`.
- Blocking-row error message: `"Row {blocking_id} is already awaiting your description of the issue — resolve it before flagging another row."`
- Frontend tooltip when blocked by another row: `"Resolve the flag on row {blockingRowId} first"`.
- No schema change, no new endpoint, no new `GET /chart` response field.

---

### Task 1: Backend — session-wide flag guard

**Files:**
- Modify: `backend/app/services/chart_service.py:252-265` (`set_flagged`)
- Test: `backend/tests/test_chart_service.py`

**Interfaces:**
- Consumes: `_get_row(conn, sid, row_id)` (existing helper, same file, returns `sqlite3.Row`), `ApiError(status, code, message)` from `app.errors`.
- Produces: `set_flagged(sid: str, row_id: int) -> None` — same signature as before, called by `row_router.flag_row` (`backend/app/routers/row_router.py:40`, unchanged).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_chart_service.py` (after `test_flag_then_reflag_conflict_and_clears_after_message`):

```python
def test_flag_blocks_flagging_other_row_until_resolved(client, sid):
    _generate(client, sid)
    rows = client.get(f"/session/{sid}/chart").json()["rows"]
    row_id_1 = rows[0]["id"]
    row_id_2 = rows[1]["id"]

    r = client.post(f"/session/{sid}/rows/{row_id_1}/flag")
    assert r.status_code == 200

    r = client.post(f"/session/{sid}/rows/{row_id_2}/flag")
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "already_flagged"
    assert str(row_id_1) in body["message"]

    client.post(
        f"/session/{sid}/chat/message",
        json={"content": "this is wrong", "row_id": row_id_1},
    )

    r = client.post(f"/session/{sid}/rows/{row_id_2}/flag")
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_chart_service.py::test_flag_blocks_flagging_other_row_until_resolved -v`
Expected: FAIL — the second `flag` call on `row_id_2` currently returns `200` instead of `409`, because `set_flagged` only checks the target row's own `flagged` state.

- [ ] **Step 3: Write minimal implementation**

Replace `set_flagged` in `backend/app/services/chart_service.py`:

```python
def set_flagged(sid: str, row_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_row(conn, sid, row_id)
        if row["flagged"]:
            raise ApiError(
                409,
                "already_flagged",
                f"Row {row_id} is already awaiting your description of the issue.",
            )
        blocking = conn.execute(
            "SELECT id FROM rows WHERE session_id = ? AND flagged = 1", (sid,)
        ).fetchone()
        if blocking is not None:
            raise ApiError(
                409,
                "already_flagged",
                f"Row {blocking['id']} is already awaiting your description of "
                "the issue — resolve it before flagging another row.",
            )
        conn.execute("UPDATE rows SET flagged = 1 WHERE id = ?", (row_id,))
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_chart_service.py -v`
Expected: All tests in the file PASS, including the new
`test_flag_blocks_flagging_other_row_until_resolved` and the pre-existing
`test_flag_then_reflag_conflict_and_clears_after_message` (same-row case
still works unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chart_service.py backend/tests/test_chart_service.py
git commit -m "Block flagging a second row while another is unresolved"
```

---

### Task 2: Frontend — disable Flag icon while another row is flagged

**Files:**
- Modify: `frontend/src/components/ChartPanel/FlagIcon.tsx`

**Interfaces:**
- Consumes: `useSessionState()` from `frontend/src/context/SessionContext.tsx` — `SessionState.chart: { rows: Row[] }` (already exists, no change needed). `Row.flagged: boolean`, `Row.id: number` from `frontend/src/types/index.ts` (unchanged). `ApiError` class from `frontend/src/types/index.ts` (unchanged) — has `.code` and `.message`.
- Produces: `FlagIcon({ row }: { row: Row })` — same exported signature and same call site in `frontend/src/components/ChartPanel/ChartRow.tsx:50` (unchanged).

- [ ] **Step 1: Replace the component implementation**

Replace the full contents of `frontend/src/components/ChartPanel/FlagIcon.tsx`:

```tsx
import { useState } from "react";
import { Flag } from "lucide-react";
import { flagRow, getChart } from "../../api/client";
import { ApiError, Row } from "../../types";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function FlagIcon({ row }: { row: Row }) {
  const { sessionId, chart } = useSessionState();
  const dispatch = useSessionDispatch();
  const [error, setError] = useState<string | null>(null);

  const blockingRow = chart.rows.find((r) => r.id !== row.id && r.flagged);
  const disabled = row.flagged || Boolean(blockingRow);

  async function handleFlag(e: React.MouseEvent) {
    e.stopPropagation();
    if (!sessionId || disabled) return;
    setError(null);

    try {
      const { system_note } = await flagRow(sessionId, row.id);
      dispatch({ type: "MESSAGE_RECEIVED", message: system_note });
      dispatch({ type: "ROW_CHIP_STAGED", rowId: row.id });

      const { rows } = await getChart(sessionId);
      dispatch({ type: "CHART_REFRESHED", rows });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Flag failed.");
    }
  }

  const tooltip = blockingRow
    ? `Resolve the flag on row ${blockingRow.id} first`
    : "Flag for re-scan";

  return (
    <div className="relative">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={handleFlag}
            disabled={disabled}
          >
            <Flag
              className={cn(
                "size-4",
                row.flagged ? "fill-orange-400 text-orange-500" : "text-muted-foreground"
              )}
            />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{tooltip}</TooltipContent>
      </Tooltip>
      {error && (
        <p
          role="alert"
          className="absolute top-full left-0 z-10 mt-1 whitespace-nowrap text-xs text-destructive"
        >
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check the frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors (this project has no
separate frontend test runner — `tsc -b` inside `npm run build` is the
verification gate for frontend changes).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChartPanel/FlagIcon.tsx
git commit -m "Disable Flag icon on other rows while one row is flagged"
```

---

### Task 3: Manual verification — golden path in the browser

**Files:** none (verification only, no code changes).

**Interfaces:**
- Consumes: the running backend (`uvicorn app.main:app`, from `backend/`) and frontend (`npm run dev`, from `frontend/`) started per this project's existing dev workflow.

- [ ] **Step 1: Start backend and frontend dev servers**

Run backend: `cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload`
Run frontend (separate terminal): `cd frontend && npm run dev`

- [ ] **Step 2: Walk the golden path**

In the browser: create/reset a session, upload a chart CSV and an
evidence `.txt`/URL, click Generate. Then:
1. Click the Flag icon on row 1. Confirm its icon turns orange/filled
   and the `FlaggedBanner` ("Awaiting your description of the issue in
   chat.") appears on row 1.
2. Hover the Flag icon on row 2 (a different row). Confirm the tooltip
   reads `"Resolve the flag on row 1 first"` (substituting row 1's
   actual id) and the button is disabled (click does nothing).
3. In chat, send a message with row 1's `@Row` chip attached (e.g.
   "the evidence is wrong here") to resolve the flag.
4. Confirm row 1's flagged banner clears, and the Flag icon on row 2 is
   now enabled again with tooltip `"Flag for re-scan"`.

- [ ] **Step 3: Check for regressions**

Confirm: flagging row 1 again after it's resolved still works (repeat
step 2's flag click on row 1), and the existing accept/reject/undo
flows on other rows are unaffected by a flagged row.

- [ ] **Step 4: Report result**

No commit for this task — report back whether the golden path and the
disabled-state/tooltip behavior worked as expected, or describe exactly
what broke.

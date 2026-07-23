import { acceptRow, getChart, rejectRow } from "../../api/client";
import { ApiError, Row } from "../../types";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";

async function silentRefetchOn409(
  sessionId: string,
  expectedCode: string,
  err: unknown,
  onRows: (rows: Row[]) => void
) {
  if (err instanceof ApiError && err.code === expectedCode) {
    const { rows } = await getChart(sessionId);
    onRows(rows);
    return;
  }
  throw err;
}

export function PendingBanner({ row }: { row: Row }) {
  const { sessionId } = useSessionState();
  const dispatch = useSessionDispatch();

  function refreshRows(rows: Row[]) {
    dispatch({ type: "CHART_REFRESHED", rows });
  }

  async function handleAccept(e: React.MouseEvent) {
    e.stopPropagation();
    if (!sessionId) return;
    try {
      await acceptRow(sessionId, row.id);
      const { rows } = await getChart(sessionId);
      refreshRows(rows);
    } catch (err) {
      await silentRefetchOn409(sessionId, "no_pending_proposal", err, refreshRows);
    }
  }

  async function handleReject(e: React.MouseEvent) {
    e.stopPropagation();
    if (!sessionId) return;
    try {
      await rejectRow(sessionId, row.id);
      const { rows } = await getChart(sessionId);
      refreshRows(rows);
    } catch (err) {
      await silentRefetchOn409(sessionId, "no_pending_proposal", err, refreshRows);
    }
  }

  function handleModify(e: React.MouseEvent) {
    e.stopPropagation();
    dispatch({ type: "ROW_CHIP_STAGED", rowId: row.id });
  }

  return (
    <div className="space-y-1.5 rounded-md border border-border/60 bg-card p-2.5">
      <p className="text-xs font-medium text-foreground">Proposed: {row.pending_value}</p>
      <p className="text-xs text-muted-foreground">{row.pending_reasoning}</p>
      <div className="flex gap-1.5">
        <Button type="button" size="xs" onClick={handleAccept}>
          Accept
        </Button>
        <Button type="button" size="xs" variant="outline" onClick={handleReject}>
          Reject
        </Button>
        <Button type="button" size="xs" variant="ghost" onClick={handleModify}>
          Modify
        </Button>
      </div>
    </div>
  );
}

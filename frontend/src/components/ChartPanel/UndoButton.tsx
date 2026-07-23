import { useState } from "react";
import { Undo2 } from "lucide-react";
import { getChart, undoRow } from "../../api/client";
import { ApiError, Row } from "../../types";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function UndoButton({ row }: { row: Row }) {
  const { sessionId } = useSessionState();
  const dispatch = useSessionDispatch();
  const enabled = row.previous_product_feature != null;
  const [confirming, setConfirming] = useState(false);

  async function performUndo(e: React.MouseEvent) {
    e.stopPropagation();
    setConfirming(false);
    if (!sessionId) return;

    try {
      await undoRow(sessionId, row.id);
      const { rows } = await getChart(sessionId);
      dispatch({ type: "CHART_REFRESHED", rows });
    } catch (err) {
      if (err instanceof ApiError && err.code === "no_undo_available") {
        const { rows } = await getChart(sessionId);
        dispatch({ type: "CHART_REFRESHED", rows });
        return;
      }
      throw err;
    }
  }

  if (confirming) {
    return (
      <div className="flex items-center gap-1 text-xs whitespace-nowrap">
        <span className="text-muted-foreground">Undo?</span>
        <Button type="button" size="xs" variant="destructive" onClick={performUndo}>
          Confirm
        </Button>
        <Button
          type="button"
          size="xs"
          variant="ghost"
          onClick={(e) => {
            e.stopPropagation();
            setConfirming(false);
          }}
        >
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={(e) => {
            e.stopPropagation();
            setConfirming(true);
          }}
          disabled={!enabled}
        >
          <Undo2 className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Undo last change</TooltipContent>
    </Tooltip>
  );
}

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

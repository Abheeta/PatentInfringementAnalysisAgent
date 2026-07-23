import { Flag } from "lucide-react";
import { flagRow, getChart } from "../../api/client";
import { Row } from "../../types";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function FlagIcon({ row }: { row: Row }) {
  const { sessionId } = useSessionState();
  const dispatch = useSessionDispatch();

  async function handleFlag(e: React.MouseEvent) {
    e.stopPropagation();
    if (!sessionId || row.flagged) return;

    const { system_note } = await flagRow(sessionId, row.id);
    dispatch({ type: "MESSAGE_RECEIVED", message: system_note });
    dispatch({ type: "ROW_CHIP_STAGED", rowId: row.id });

    const { rows } = await getChart(sessionId);
    dispatch({ type: "CHART_REFRESHED", rows });
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={handleFlag}
          disabled={row.flagged}
        >
          <Flag
            className={cn(
              "size-4",
              row.flagged ? "fill-orange-400 text-orange-500" : "text-muted-foreground"
            )}
          />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Flag for re-scan</TooltipContent>
    </Tooltip>
  );
}

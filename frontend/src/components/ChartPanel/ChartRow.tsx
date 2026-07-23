import { Row } from "../../types";
import { useSessionDispatch } from "../../context/SessionContext";
import { PendingBanner } from "./PendingBanner";
import { FlaggedBanner } from "./FlaggedBanner";
import { UndoButton } from "./UndoButton";
import { FlagIcon } from "./FlagIcon";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const TIER_STYLES: Record<string, string> = {
  Strong: "border-green-200 bg-green-100 text-green-800",
  Moderate: "border-amber-200 bg-amber-100 text-amber-800",
  Weak: "border-red-200 bg-red-100 text-red-800",
};

export function ChartRow({ row }: { row: Row }) {
  const dispatch = useSessionDispatch();

  return (
    <tr
      onClick={() => dispatch({ type: "ROW_CHIP_STAGED", rowId: row.id })}
      className="cursor-pointer border-b border-border/50 align-top hover:bg-accent/40"
    >
      <td className="max-w-[16rem] px-4 py-3 font-medium text-foreground">
        {row.claim_element}
      </td>
      <td className="max-w-[16rem] px-4 py-3 text-muted-foreground">
        {row.product_feature}
      </td>
      <td className="max-w-[20rem] px-4 py-3 text-muted-foreground">
        {row.ai_reasoning}
      </td>
      <td className="px-4 py-3">
        {row.confidence && (
          <Badge variant="outline" className={cn(TIER_STYLES[row.confidence])}>
            {row.confidence}
          </Badge>
        )}
      </td>
      <td className="px-4 py-3">
        {row.pending_value != null ? (
          <PendingBanner row={row} />
        ) : row.flagged ? (
          <FlaggedBanner />
        ) : null}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <UndoButton row={row} />
          <FlagIcon row={row} />
        </div>
      </td>
    </tr>
  );
}

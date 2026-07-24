import { Badge } from "@/components/ui/badge";
import { useSessionState } from "../../context/SessionContext";
import { toDisplayRowId } from "../../lib/rowDisplay";

export function RowChip({ rowId }: { rowId: number }) {
  const { chart } = useSessionState();
  return (
    <Badge variant="secondary" className="mr-1 font-normal">
      @Row[{toDisplayRowId(chart.rows, rowId)}]
    </Badge>
  );
}

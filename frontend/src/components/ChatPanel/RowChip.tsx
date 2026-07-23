import { Badge } from "@/components/ui/badge";

export function RowChip({ rowId }: { rowId: number }) {
  return (
    <Badge variant="secondary" className="mr-1 font-normal">
      @Row[{rowId}]
    </Badge>
  );
}

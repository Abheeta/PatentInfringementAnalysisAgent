import { useSessionState } from "../../context/SessionContext";
import { ChartRow } from "./ChartRow";
import { ScrollArea } from "@/components/ui/scroll-area";

export function ChartPanel() {
  const { chart } = useSessionState();

  return (
    <div className="flex h-full flex-col border-r border-border/60 bg-chart-surface">
      <div className="border-b border-border/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-foreground">Claim Chart</h2>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-chart-surface">
            <tr className="border-b border-border/60 text-left text-xs font-medium tracking-wide text-muted-foreground uppercase">
              <th className="px-4 py-2 font-medium">Claim Element</th>
              <th className="px-4 py-2 font-medium">Evidence</th>
              <th className="px-4 py-2 font-medium">Reasoning</th>
              <th className="px-4 py-2 font-medium">Confidence</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {chart.rows.map((row) => (
              <ChartRow key={row.id} row={row} />
            ))}
          </tbody>
        </table>
      </ScrollArea>
    </div>
  );
}

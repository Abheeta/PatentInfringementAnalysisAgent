import { Download } from "lucide-react";
import { exportChart } from "../../api/client";
import { useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ExportButton() {
  const { sessionId, generated } = useSessionState();

  async function handleExport() {
    if (!sessionId) return;
    const blob = await exportChart(sessionId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "claim_chart.docx";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={handleExport}
          disabled={!generated}
        >
          <Download className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Export .docx</TooltipContent>
    </Tooltip>
  );
}

import { useRef, useState } from "react";
import { Check, FileSpreadsheet } from "lucide-react";
import { getChart, uploadChart } from "../api/client";
import { ApiError } from "../types";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function UploadChartButton() {
  const { sessionId, chartUploaded } = useSessionState();
  const dispatch = useSessionDispatch();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !sessionId) return;
    setError(null);
    try {
      await uploadChart(sessionId, file);
      const { rows } = await getChart(sessionId);
      dispatch({ type: "CHART_REFRESHED", rows });
      dispatch({ type: "CHART_UPLOADED" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  return (
    <div className="relative">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant={chartUploaded ? "secondary" : "outline"}
            size="icon"
            onClick={() => inputRef.current?.click()}
            disabled={chartUploaded}
          >
            {chartUploaded ? (
              <Check className="size-4" />
            ) : (
              <FileSpreadsheet className="size-4" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {chartUploaded ? "Chart uploaded" : "Upload chart (.csv)"}
        </TooltipContent>
      </Tooltip>
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleFileChange}
      />
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

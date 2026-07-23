import { useRef, useState } from "react";
import { Check, FileSpreadsheet } from "lucide-react";
import { getChart, uploadChart } from "../api/client";
import { ApiError } from "../types";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function UploadChartButton({ variant = "icon" }: { variant?: "icon" | "tile" }) {
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

  const trigger =
    variant === "tile" ? (
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={chartUploaded}
        className={cn(
          "flex flex-1 flex-col items-center justify-center gap-1.5 rounded-md border py-3.5 text-center transition-colors",
          chartUploaded
            ? "border-border/60 bg-secondary/60 text-secondary-foreground"
            : "border-border bg-background hover:bg-accent hover:text-accent-foreground"
        )}
      >
        {chartUploaded ? (
          <Check className="size-5 text-emerald-600 dark:text-emerald-400" />
        ) : (
          <FileSpreadsheet className="size-5" />
        )}
        <span className="text-xs font-medium">
          {chartUploaded ? "Chart uploaded" : "Upload Chart"}
        </span>
        {!chartUploaded && (
          <span className="text-[11px] text-muted-foreground">.csv file</span>
        )}
      </button>
    ) : (
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
    );

  return (
    <div className={cn("relative", variant === "tile" && "flex flex-1")}>
      {trigger}
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

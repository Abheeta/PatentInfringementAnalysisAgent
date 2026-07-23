import { useState } from "react";
import { Sparkles } from "lucide-react";
import { generate, getChart } from "../api/client";
import { ApiError } from "../types";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function GenerateButton({ variant = "icon" }: { variant?: "icon" | "tile" }) {
  const { sessionId, chartUploaded, evidenceUploaded } = useSessionState();
  const dispatch = useSessionDispatch();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const ready = chartUploaded && evidenceUploaded;

  async function handleGenerate() {
    if (!sessionId || !ready) return;
    setError(null);
    setLoading(true);
    try {
      const { opening_message } = await generate(sessionId);
      const { rows } = await getChart(sessionId);
      dispatch({ type: "CHART_REFRESHED", rows });
      dispatch({ type: "GENERATED", openingMessage: opening_message });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Generate failed.");
    } finally {
      setLoading(false);
    }
  }

  if (variant === "tile") {
    let caption = "Ready to generate";
    if (!chartUploaded && !evidenceUploaded) caption = "Upload a chart and evidence first";
    else if (!chartUploaded) caption = "Upload a chart first";
    else if (!evidenceUploaded) caption = "Add evidence first";

    return (
      <div className="relative flex flex-1">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={!ready || loading}
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-1.5 rounded-md border py-3.5 text-center transition-colors",
            ready
              ? "border-primary/40 bg-primary text-primary-foreground hover:bg-primary/90"
              : "border-border bg-background text-muted-foreground"
          )}
        >
          <Sparkles className="size-5" />
          <span className="text-xs font-medium">
            {loading ? "Generating…" : "Generate"}
          </span>
          <span className={cn("text-[11px]", ready ? "text-primary-foreground/80" : "text-muted-foreground")}>
            {caption}
          </span>
        </button>
        {error && (
          <p
            role="alert"
            className="absolute top-full right-0 z-10 mt-1 whitespace-nowrap text-xs text-destructive"
          >
            {error}{" "}
            <button type="button" className="underline" onClick={handleGenerate}>
              Retry
            </button>
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      <Button
        type="button"
        size="sm"
        onClick={handleGenerate}
        disabled={!ready || loading}
        className="gap-1.5"
      >
        <Sparkles className="size-4" />
        {loading ? "Generating…" : "Generate"}
      </Button>
      {error && (
        <p
          role="alert"
          className="absolute top-full right-0 z-10 mt-1 whitespace-nowrap text-xs text-destructive"
        >
          {error}{" "}
          <button type="button" className="underline" onClick={handleGenerate}>
            Retry
          </button>
        </p>
      )}
    </div>
  );
}

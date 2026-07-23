import { useState } from "react";
import { Sparkles } from "lucide-react";
import { generate, getChart } from "../api/client";
import { ApiError } from "../types";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Button } from "@/components/ui/button";

export function GenerateButton() {
  const { sessionId, chartUploaded } = useSessionState();
  const dispatch = useSessionDispatch();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleGenerate() {
    if (!sessionId) return;
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

  return (
    <div className="relative">
      <Button
        type="button"
        size="sm"
        onClick={handleGenerate}
        disabled={!chartUploaded || loading}
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

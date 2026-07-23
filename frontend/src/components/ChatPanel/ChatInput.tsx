import { useState } from "react";
import { Send } from "lucide-react";
import { getChart, sendChatMessage } from "../../api/client";
import { ApiError } from "../../types";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { RowChip } from "./RowChip";
import { GenerateBar } from "./GenerateBar";
import { UploadEvidenceButton } from "../UploadEvidenceButton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function ChatInput({
  sending,
  setSending,
}: {
  sending: boolean;
  setSending: (sending: boolean) => void;
}) {
  const { sessionId, pendingRowId, generated } = useSessionState();
  const dispatch = useSessionDispatch();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!sessionId || !text.trim() || sending) return;
    setError(null);
    setSending(true);

    const content = text.trim();
    dispatch({
      type: "MESSAGE_SENT",
      message: {
        id: Date.now(),
        role: "user",
        content,
        row_id: pendingRowId,
        created_at: new Date().toISOString(),
      },
    });
    setText("");

    try {
      const { assistant_message, refresh_chart } = await sendChatMessage(sessionId, {
        content,
        row_id: pendingRowId,
      });
      dispatch({ type: "MESSAGE_RECEIVED", message: assistant_message });
      if (refresh_chart) {
        const { rows } = await getChart(sessionId);
        dispatch({ type: "CHART_REFRESHED", rows });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Message failed to send.");
    } finally {
      setSending(false);
    }
  }

  if (!generated) {
    return <GenerateBar />;
  }

  return (
    <div className="border-t border-border/60 px-4 py-3">
      {pendingRowId != null && (
        <div className="mb-2">
          <RowChip rowId={pendingRowId} />
        </div>
      )}
      <div className="flex items-center gap-2">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          disabled={sending}
          placeholder="Ask about a claim element, or click a row first…"
          className="bg-background"
        />
        <UploadEvidenceButton variant="icon" />
        <Button
          type="button"
          size="icon"
          onClick={handleSubmit}
          disabled={sending || !text.trim()}
        >
          <Send className="size-4" />
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-1.5 text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

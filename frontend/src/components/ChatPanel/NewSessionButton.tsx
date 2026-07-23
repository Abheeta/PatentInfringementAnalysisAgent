import { useState } from "react";
import { Plus } from "lucide-react";
import { createSession } from "../../api/client";
import { SESSION_STORAGE_KEY } from "../../App";
import { useSessionDispatch, useSessionState } from "../../context/SessionContext";
import { Button } from "@/components/ui/button";

export function NewSessionButton() {
  const { chartUploaded, chatMessages } = useSessionState();
  const dispatch = useSessionDispatch();
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (chartUploaded || chatMessages.length > 0) {
      const confirmed = window.confirm(
        "Start a new session? This will clear the current chart and chat."
      );
      if (!confirmed) return;
    }

    setLoading(true);
    try {
      const { session_id } = await createSession();
      localStorage.setItem(SESSION_STORAGE_KEY, session_id);
      dispatch({ type: "SESSION_RESET", sessionId: session_id });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={handleClick}
      disabled={loading}
    >
      <Plus className="size-4" />
      New Session
    </Button>
  );
}

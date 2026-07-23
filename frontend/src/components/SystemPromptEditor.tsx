import { useEffect, useState } from "react";
import { putSystemPrompt } from "../api/client";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export function SystemPromptEditor() {
  const { sessionId, systemPromptDraft } = useSessionState();
  const dispatch = useSessionDispatch();
  const [text, setText] = useState(systemPromptDraft);
  const [saved, setSaved] = useState(false);

  // Syncs the textarea once the session's saved prompt loads asynchronously
  // (fetched by the top-level App mount effect after this component mounts).
  useEffect(() => {
    setText(systemPromptDraft);
  }, [systemPromptDraft]);

  async function handleSave() {
    if (!sessionId) return;
    await putSystemPrompt(sessionId, text);
    dispatch({ type: "SYSTEM_PROMPT_SAVED", text });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="system-prompt">Analyst instructions (optional)</Label>
      <Textarea
        id="system-prompt"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
      />
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" onClick={handleSave}>
          Save
        </Button>
        {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { FileText } from "lucide-react";
import { uploadEvidence } from "../api/client";
import { ApiError } from "../types";
import { useSessionDispatch, useSessionState } from "../context/SessionContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function UploadEvidenceButton() {
  const { sessionId, chartUploaded } = useSessionState();
  const dispatch = useSessionDispatch();
  const inputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !sessionId) return;
    setError(null);
    try {
      await uploadEvidence(sessionId, { file });
      dispatch({ type: "EVIDENCE_UPLOADED" });
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  async function handleUrlSubmit() {
    if (!sessionId || !url.trim()) return;
    setError(null);
    try {
      await uploadEvidence(sessionId, { url: url.trim() });
      dispatch({ type: "EVIDENCE_UPLOADED" });
      setUrl("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Fetch failed.");
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="icon" disabled={!chartUploaded}>
              <FileText className="size-4" />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>Add evidence</TooltipContent>
      </Tooltip>
      <PopoverContent className="w-72 space-y-3" align="start">
        <div className="space-y-1.5">
          <p className="text-sm font-medium">Add evidence</p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full justify-start"
            onClick={() => inputRef.current?.click()}
          >
            Upload .txt file
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept=".txt"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs text-muted-foreground">or</span>
          <div className="h-px flex-1 bg-border" />
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="Paste a URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleUrlSubmit();
            }}
          />
          <Button type="button" size="sm" onClick={handleUrlSubmit} disabled={!url.trim()}>
            Add
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

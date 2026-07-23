import { UploadChartButton } from "../UploadChartButton";
import { UploadEvidenceButton } from "../UploadEvidenceButton";
import { GenerateButton } from "../GenerateButton";

export function GenerateBar() {
  return (
    <div className="border-t border-border/60 px-4 py-3">
      <p className="mb-2 text-xs text-muted-foreground">
        Upload a claim chart and at least one piece of evidence, then generate to start chatting.
      </p>
      <div className="flex items-stretch gap-2">
        <UploadChartButton variant="tile" />
        <UploadEvidenceButton variant="tile" />
        <GenerateButton variant="tile" />
      </div>
    </div>
  );
}

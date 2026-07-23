import { UploadChartButton } from "../UploadChartButton";
import { UploadEvidenceButton } from "../UploadEvidenceButton";
import { GenerateButton } from "../GenerateButton";
import { SettingsButton } from "./SettingsButton";
import { ExportButton } from "./ExportButton";

export function ChatToolbar() {
  return (
    <div className="flex items-center gap-2 border-b border-border/60 bg-toolbar-surface px-4 py-2.5">
      <UploadChartButton />
      <UploadEvidenceButton />
      <SettingsButton />
      <div className="ml-auto flex items-center gap-2">
        <GenerateButton />
        <ExportButton />
      </div>
    </div>
  );
}

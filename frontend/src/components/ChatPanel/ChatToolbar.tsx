import { SettingsButton } from "./SettingsButton";
import { ExportButton } from "./ExportButton";
import { NewSessionButton } from "./NewSessionButton";

export function ChatToolbar() {
  return (
    <div className="flex items-center gap-2 border-b border-border/60 bg-toolbar-surface px-4 py-2.5">
      <NewSessionButton />
      <div className="ml-auto flex items-center gap-2">
        <SettingsButton />
        <ExportButton />
      </div>
    </div>
  );
}

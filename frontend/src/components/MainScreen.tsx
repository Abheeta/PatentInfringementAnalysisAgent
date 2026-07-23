import { useSessionState } from "../context/SessionContext";
import { ChartPanel } from "./ChartPanel/ChartPanel";
import { ChatPanel } from "./ChatPanel/ChatPanel";
import { cn } from "@/lib/utils";

export function MainScreen() {
  const { chartUploaded } = useSessionState();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <div
        className={cn(
          "h-full min-w-0 overflow-hidden transition-[width] duration-300 ease-out",
          chartUploaded ? "w-[58%]" : "w-0"
        )}
      >
        {chartUploaded && <ChartPanel />}
      </div>
      <div
        className={cn(
          "h-full min-w-0 transition-[width] duration-300 ease-out",
          chartUploaded ? "w-[42%]" : "w-full"
        )}
      >
        <ChatPanel />
      </div>
    </div>
  );
}

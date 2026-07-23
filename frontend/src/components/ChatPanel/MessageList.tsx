import { useSessionState } from "../../context/SessionContext";
import { RowChip } from "./RowChip";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function MessageList({ thinking }: { thinking: boolean }) {
  const { chatMessages } = useSessionState();

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-3 px-4 py-4">
        {chatMessages.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Upload a claim chart to get started.
          </p>
        )}
        {chatMessages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed shadow-sm",
              message.role === "user"
                ? "self-end bg-primary text-primary-foreground"
                : "self-start bg-card text-card-foreground"
            )}
          >
            {message.row_id != null && <RowChip rowId={message.row_id} />}
            <span className="whitespace-pre-wrap">{message.content}</span>
          </div>
        ))}
        {thinking && (
          <div className="flex max-w-[85%] items-center gap-1 self-start rounded-lg bg-card px-3 py-2 text-sm text-muted-foreground shadow-sm">
            <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-current" />
          </div>
        )}
      </div>
    </ScrollArea>
  );
}

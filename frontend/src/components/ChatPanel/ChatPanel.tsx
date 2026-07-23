import { useState } from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ChatToolbar } from "./ChatToolbar";

export function ChatPanel() {
  const [sending, setSending] = useState(false);

  return (
    <div className="flex h-full flex-col bg-chat-surface">
      <ChatToolbar />
      <MessageList thinking={sending} />
      <ChatInput sending={sending} setSending={setSending} />
    </div>
  );
}

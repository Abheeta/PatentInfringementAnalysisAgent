import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ChatToolbar } from "./ChatToolbar";

export function ChatPanel() {
  return (
    <div className="flex h-full flex-col bg-chat-surface">
      <ChatToolbar />
      <MessageList />
      <ChatInput />
    </div>
  );
}

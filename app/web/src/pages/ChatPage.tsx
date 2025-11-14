import { MessageList } from '../components/chat/MessageList';
import { ChatInput } from '../components/chat/ChatInput';
import { useChat } from '../hooks/useChat';
import './ChatPage.css';

export default function ChatPage() {
  const { messages, isLoading, sendMessage } = useChat();

  return (
    <div className="chat-page">
      <MessageList messages={messages} isLoading={isLoading} />
      <ChatInput onSendMessage={sendMessage} disabled={isLoading} />
    </div>
  );
}

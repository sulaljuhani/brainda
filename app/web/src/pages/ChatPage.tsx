import { useState, useEffect, useCallback } from 'react';
import { MessageList } from '../components/chat/MessageList';
import { ChatInput } from '../components/chat/ChatInput';
import { useChat } from '../hooks/useChat';
import { useConversation } from '../hooks/useConversation';
import './ChatPage.css';

export default function ChatPage() {
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const { messages: loadedMessages, isLoading: isLoadingConversation } = useConversation(selectedConversationId);

  const {
    messages,
    isLoading,
    sendMessage,
    clearMessages,
    loadMessages,
  } = useChat({
    conversationId: selectedConversationId,
    onConversationCreated: (newConversationId) => {
      setSelectedConversationId(newConversationId);
    },
  });

  // Load messages when conversation is selected
  useEffect(() => {
    if (loadedMessages.length > 0 && !isLoadingConversation) {
      loadMessages(loadedMessages);
    }
  }, [loadedMessages, isLoadingConversation, loadMessages]);

  const handleConversationSelect = useCallback((conversationId: string) => {
    setSelectedConversationId(conversationId);
  }, []);

  const handleNewConversation = useCallback(() => {
    setSelectedConversationId(null);
    clearMessages();
  }, [clearMessages]);

  // Expose handlers to parent (MainLayout) via window for sidebar integration
  useEffect(() => {
    (window as any).__chatPageHandlers = {
      currentConversationId: selectedConversationId,
      onConversationSelect: handleConversationSelect,
      onNewConversation: handleNewConversation,
    };
    return () => {
      delete (window as any).__chatPageHandlers;
    };
  }, [selectedConversationId, handleConversationSelect, handleNewConversation]);

  return (
    <div className="chat-page">
      <MessageList messages={messages} isLoading={isLoading || isLoadingConversation} />
      <ChatInput onSendMessage={sendMessage} disabled={isLoading || isLoadingConversation} />
    </div>
  );
}

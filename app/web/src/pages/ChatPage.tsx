import { useState, useEffect } from 'react';
import { MessageList } from '../components/chat/MessageList';
import { ChatInput } from '../components/chat/ChatInput';
import { ChatHistorySidebar } from '../components/chat/ChatHistorySidebar';
import { useChat } from '../hooks/useChat';
import { useConversation } from '../hooks/useConversation';
import './ChatPage.css';

const SUGGESTED_PROMPTS = [
  {
    icon: '✓',
    title: 'Create a task',
    prompt: 'Create a task to review the quarterly report by Friday',
  },
  {
    icon: '📅',
    title: 'Schedule an event',
    prompt: 'Schedule a team meeting tomorrow at 2pm',
  },
  {
    icon: '⏰',
    title: 'Set a reminder',
    prompt: 'Remind me to call the client 2 days before the meeting',
  },
  {
    icon: '🔎',
    title: 'Search your notes',
    prompt: 'What did I write about the project proposal?',
  },
];

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

  const handleSuggestionClick = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleConversationSelect = (conversationId: string) => {
    setSelectedConversationId(conversationId);
  };

  const handleNewConversation = () => {
    setSelectedConversationId(null);
    clearMessages();
  };

  const showWelcome = messages.length === 0 && !isLoading && !isLoadingConversation;

  return (
    <div className="chat-page-container">
      <ChatHistorySidebar
        currentConversationId={selectedConversationId}
        onConversationSelect={handleConversationSelect}
        onNewConversation={handleNewConversation}
      />
      <div className="chat-page">
        <div className="chat-page__header">
          <div className="chat-page__header-content">
            <h1 className="chat-page__title">Chat</h1>
            <p className="chat-page__subtitle">
              Ask questions, create tasks, or manage your schedule
            </p>
          </div>
          {messages.length > 0 && (
            <button
              className="chat-page__clear-btn"
              onClick={handleNewConversation}
              aria-label="New conversation"
            >
              New Chat
            </button>
          )}
        </div>

        {showWelcome && (
          <div className="chat-page__welcome">
            <div className="chat-page__welcome-icon">💬</div>
            <h2 className="chat-page__welcome-title">How can I help you today?</h2>
            <p className="chat-page__welcome-subtitle">
              I can help you manage tasks, events, reminders, and answer questions about your notes.
            </p>

            <div className="chat-page__suggestions">
              {SUGGESTED_PROMPTS.map((suggestion, index) => (
                <button
                  key={index}
                  className="chat-page__suggestion"
                  onClick={() => handleSuggestionClick(suggestion.prompt)}
                >
                  <span className="chat-page__suggestion-icon">{suggestion.icon}</span>
                  <span className="chat-page__suggestion-title">{suggestion.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <MessageList messages={messages} isLoading={isLoading || isLoadingConversation} />
        <ChatInput onSendMessage={sendMessage} disabled={isLoading || isLoadingConversation} />
      </div>
    </div>
  );
}

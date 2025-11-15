import { useChatConversations } from '../../hooks/useChatConversations';
import { ConversationItem } from './ConversationItem';
import { NewConversationButton } from './NewConversationButton';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { History } from 'lucide-react';
import './ChatHistorySidebar.css';

interface ChatHistorySidebarProps {
  currentConversationId: string | null;
  onConversationSelect: (conversationId: string) => void;
  onNewConversation: () => void;
}

export function ChatHistorySidebar({
  currentConversationId,
  onConversationSelect,
  onNewConversation,
}: ChatHistorySidebarProps) {
  const { conversations, isLoading, error, deleteConversation } = useChatConversations();

  const handleDelete = async (conversationId: string) => {
    await deleteConversation(conversationId);
    // If deleted conversation was active, start a new one
    if (conversationId === currentConversationId) {
      onNewConversation();
    }
  };

  return (
    <div className="chat-history-sidebar">
      <div className="chat-history-sidebar__header">
        <div className="chat-history-sidebar__title">
          <History size={20} />
          <span>Chat History</span>
        </div>
      </div>

      <div className="chat-history-sidebar__new">
        <NewConversationButton onClick={onNewConversation} />
      </div>

      <div className="chat-history-sidebar__content">
        {isLoading && (
          <div className="chat-history-sidebar__loading">
            <LoadingSpinner />
          </div>
        )}

        {error && (
          <div className="chat-history-sidebar__error">
            Failed to load conversations
          </div>
        )}

        {!isLoading && !error && conversations.length === 0 && (
          <div className="chat-history-sidebar__empty">
            <p>No conversations yet</p>
            <p className="chat-history-sidebar__empty-hint">
              Start a new conversation to begin
            </p>
          </div>
        )}

        {!isLoading && !error && conversations.length > 0 && (
          <div className="chat-history-sidebar__list">
            {conversations.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === currentConversationId}
                onClick={() => onConversationSelect(conversation.id)}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

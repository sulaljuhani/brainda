import { useState } from 'react';
import { MessageSquare, Trash2 } from 'lucide-react';
import type { ChatConversation } from '@/types';
import './ConversationItem.css';

interface ConversationItemProps {
  conversation: ChatConversation;
  isActive?: boolean;
  onClick: () => void;
  onDelete: (id: string) => void;
}

export function ConversationItem({
  conversation,
  isActive = false,
  onClick,
  onDelete,
}: ConversationItemProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    setIsDeleting(true);
    try {
      await onDelete(conversation.id);
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div
      className={`conversation-item ${isActive ? 'conversation-item--active' : ''} ${
        isDeleting ? 'conversation-item--deleting' : ''
      }`}
      onClick={onClick}
    >
      <div className="conversation-item__icon">
        <MessageSquare size={18} />
      </div>
      <div className="conversation-item__content">
        <div className="conversation-item__title">{conversation.title}</div>
        <div className="conversation-item__meta">
          {conversation.message_count || 0} messages · {formatDate(conversation.updated_at)}
        </div>
      </div>
      <button
        className="conversation-item__delete"
        onClick={handleDelete}
        disabled={isDeleting}
        aria-label="Delete conversation"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}

import { PlusCircle } from 'lucide-react';
import './NewConversationButton.css';

interface NewConversationButtonProps {
  onClick: () => void;
}

export function NewConversationButton({ onClick }: NewConversationButtonProps) {
  return (
    <button className="new-conversation-btn" onClick={onClick}>
      <PlusCircle size={20} />
      <span>New Conversation</span>
    </button>
  );
}

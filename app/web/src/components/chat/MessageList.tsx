import { useEffect, useRef } from 'react';
import { MessageSquare } from 'lucide-react';
import type { ChatMessage } from '@types/*';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import './MessageList.css';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading = false }: MessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="message-list message-list--empty">
        <div className="message-list__empty-state">
          <MessageSquare size={48} strokeWidth={1.5} />
          <h2>Welcome to Brainda</h2>
          <p>Start a conversation by asking a question or sharing your thoughts.</p>
          <div className="message-list__suggestions">
            <div className="message-list__suggestion">
              What can you help me with?
            </div>
            <div className="message-list__suggestion">
              Search my notes
            </div>
            <div className="message-list__suggestion">
              What's on my calendar today?
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      <div className="message-list__messages">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isLoading && (
          <div className="message-list__typing">
            <div className="message-bubble__avatar message-bubble__avatar--assistant">
              <MessageSquare size={20} />
            </div>
            <TypingIndicator />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

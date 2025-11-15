import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { format } from 'date-fns';
import { Copy, Check, User, Bot } from 'lucide-react';
import type { ChatMessage } from '@/types';
import { CitationInline } from './CitationInline';
import { ToolCallCard } from './ToolCallCard';
import './MessageBubble.css';
import 'highlight.js/styles/github-dark.css';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = message.role === 'user';

  return (
    <div className={`message-bubble message-bubble--${message.role}`}>
      <div className="message-bubble__avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>

      <div className="message-bubble__content">
        <div className="message-bubble__header">
          <span className="message-bubble__role">
            {isUser ? 'You' : 'Assistant'}
          </span>
          <span className="message-bubble__timestamp">
            {format(new Date(message.timestamp), 'h:mm a')}
          </span>
        </div>

        {message.toolCall && (
          <ToolCallCard toolCall={message.toolCall} />
        )}

        <div className="message-bubble__text">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              code: ({ node, inline, className, children, ...props }) => {
                const match = /language-(\w+)/.exec(className || '');
                return !inline ? (
                  <div className="code-block">
                    {match && (
                      <div className="code-block__language">
                        {match[1]}
                      </div>
                    )}
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </div>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.text}
          </ReactMarkdown>
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="message-bubble__citations">
            <div className="message-bubble__citations-label">Sources:</div>
            <div className="message-bubble__citations-list">
              {message.citations.map((citation, index) => (
                <CitationInline key={index} citation={citation} index={index} />
              ))}
            </div>
          </div>
        )}

        <button
          className="message-bubble__copy"
          onClick={handleCopy}
          aria-label="Copy message"
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
      </div>
    </div>
  );
}

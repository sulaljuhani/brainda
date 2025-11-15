import { useState } from 'react';
import { CheckCircle, XCircle, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import type { ToolCall } from '@/types';
import './ToolCallCard.css';

interface ToolCallCardProps {
  toolCall: ToolCall;
}

const statusIcons = {
  success: <CheckCircle size={16} />,
  error: <XCircle size={16} />,
  pending: <Clock size={16} />,
};

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={`tool-call-card tool-call-card--${toolCall.status}`}>
      <div className="tool-call-card__header">
        <div className="tool-call-card__icon">{toolCall.icon}</div>
        <div className="tool-call-card__name">{toolCall.name}</div>
        <div className="tool-call-card__status">
          {statusIcons[toolCall.status]}
        </div>
        <button
          className="tool-call-card__toggle"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {isExpanded && (
        <div className="tool-call-card__result">
          <div className="tool-call-card__result-label">Result:</div>
          <pre className="tool-call-card__result-content">{toolCall.result}</pre>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { FileText, StickyNote, Calendar, File } from 'lucide-react';
import type { Citation } from '@types/*';
import './CitationInline.css';

interface CitationInlineProps {
  citation: Citation;
  index: number;
}

const getIconForSourceType = (sourceType: string) => {
  switch (sourceType) {
    case 'note':
      return <StickyNote size={14} />;
    case 'document':
      return <FileText size={14} />;
    case 'event':
      return <Calendar size={14} />;
    default:
      return <File size={14} />;
  }
};

export function CitationInline({ citation, index }: CitationInlineProps) {
  const [showPopover, setShowPopover] = useState(false);

  return (
    <span
      className="citation-inline"
      onMouseEnter={() => setShowPopover(true)}
      onMouseLeave={() => setShowPopover(false)}
    >
      <sup className="citation-inline__number">[{index + 1}]</sup>
      {showPopover && (
        <div className="citation-inline__popover">
          <div className="citation-inline__header">
            {getIconForSourceType(citation.source_type)}
            <span className="citation-inline__type">{citation.source_type}</span>
          </div>
          <div className="citation-inline__title">{citation.source_title}</div>
          <div className="citation-inline__snippet">{citation.content_snippet}</div>
          <div className="citation-inline__score">
            Relevance: {(citation.score * 100).toFixed(0)}%
          </div>
        </div>
      )}
    </span>
  );
}

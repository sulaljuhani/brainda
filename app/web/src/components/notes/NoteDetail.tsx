import { format } from 'date-fns';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Calendar, Tag, Edit, Trash2, ArrowLeft } from 'lucide-react';
import { Button } from '@components/shared/Button';
import type { Note } from '@/types';
import './NoteDetail.css';

interface NoteDetailProps {
  note: Note;
  onEdit: () => void;
  onDelete: () => void;
  onBack: () => void;
}

export function NoteDetail({ note, onEdit, onDelete, onBack }: NoteDetailProps) {
  return (
    <div className="note-detail">
      <div className="note-detail-header">
        <Button variant="ghost" size="small" onClick={onBack}>
          <ArrowLeft size={16} />
          Back to Notes
        </Button>

        <div className="note-detail-actions">
          <Button variant="secondary" size="small" onClick={onEdit}>
            <Edit size={16} />
            Edit
          </Button>
          <Button variant="danger" size="small" onClick={onDelete}>
            <Trash2 size={16} />
            Delete
          </Button>
        </div>
      </div>

      <div className="note-detail-content">
        <h1 className="note-detail-title">{note.title}</h1>

        <div className="note-detail-meta">
          <span className="note-detail-date">
            <Calendar size={14} />
            Last updated {format(new Date(note.updated_at), 'MMM d, yyyy h:mm a')}
          </span>

          {note.tags && note.tags.length > 0 && (
            <div className="note-detail-tags">
              <Tag size={14} />
              <div className="note-detail-tags-list">
                {note.tags.map((tag) => (
                  <span key={tag} className="note-detail-tag">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="note-detail-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.body}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

import { format } from 'date-fns';
import { FileText, Calendar, Tag } from 'lucide-react';
import type { Note } from '@/types';
import './NoteCard.css';

interface NoteCardProps {
  note: Note;
  onClick: () => void;
}

export function NoteCard({ note, onClick }: NoteCardProps) {
  const preview = note.body.slice(0, 150) + (note.body.length > 150 ? '...' : '');

  return (
    <article className="note-card" onClick={onClick}>
      <div className="note-card-header">
        <div className="note-card-icon">
          <FileText size={18} />
        </div>
        <h3 className="note-card-title">{note.title}</h3>
      </div>

      {preview && <p className="note-card-preview">{preview}</p>}

      {note.tags && note.tags.length > 0 && (
        <div className="note-card-tags">
          <Tag size={14} />
          <div className="note-card-tags-list">
            {note.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="note-card-tag">
                {tag}
              </span>
            ))}
            {note.tags.length > 3 && (
              <span className="note-card-tag-more">+{note.tags.length - 3}</span>
            )}
          </div>
        </div>
      )}

      <div className="note-card-footer">
        <span className="note-card-date">
          <Calendar size={14} />
          {format(new Date(note.updated_at), 'MMM d, yyyy')}
        </span>
      </div>
    </article>
  );
}

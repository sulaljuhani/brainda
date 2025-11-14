import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Eye, EyeOff } from 'lucide-react';
import { Modal } from '@components/shared/Modal';
import { Input } from '@components/shared/Input';
import { Textarea } from '@components/shared/Textarea';
import { Button } from '@components/shared/Button';
import { TagInput } from './TagInput';
import type { Note, CreateNoteRequest } from '@types/*';
import './NoteEditor.css';

interface NoteEditorProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: CreateNoteRequest) => Promise<void>;
  note?: Note;
  allTags?: string[];
}

export function NoteEditor({ isOpen, onClose, onSave, note, allTags = [] }: NoteEditorProps) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      if (note) {
        setTitle(note.title);
        setBody(note.body);
        setTags(note.tags || []);
      } else {
        setTitle('');
        setBody('');
        setTags([]);
      }
      setShowPreview(false);
      setError('');
    }
  }, [isOpen, note]);

  const handleSave = async () => {
    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    if (!body.trim()) {
      setError('Body is required');
      return;
    }

    try {
      setSaving(true);
      setError('');
      await onSave({
        title: title.trim(),
        body: body.trim(),
        tags: tags.length > 0 ? tags : undefined,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="large">
      <div className="note-editor">
        <div className="note-editor-header">
          <h2 className="note-editor-title">{note ? 'Edit Note' : 'Create Note'}</h2>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setShowPreview(!showPreview)}
          >
            {showPreview ? (
              <>
                <EyeOff size={16} />
                Hide Preview
              </>
            ) : (
              <>
                <Eye size={16} />
                Show Preview
              </>
            )}
          </Button>
        </div>

        {error && <div className="note-editor-error">{error}</div>}

        <div className="note-editor-form">
          <Input
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter note title..."
            fullWidth
            autoFocus
          />

          <div>
            <label className="note-editor-label">Tags</label>
            <TagInput tags={tags} onChange={setTags} suggestions={allTags} />
          </div>

          <div className="note-editor-body-section">
            <label className="note-editor-label">Body</label>
            <div className="note-editor-split">
              <div className={`note-editor-edit ${showPreview ? 'note-editor-split-view' : ''}`}>
                <Textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Write your note in Markdown..."
                  rows={12}
                  fullWidth
                />
              </div>

              {showPreview && (
                <div className="note-editor-preview">
                  <div className="note-editor-preview-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{body || '*Preview will appear here...*'}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="note-editor-footer">
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save Note'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

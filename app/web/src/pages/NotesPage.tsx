import { useState, useMemo } from 'react';
import { Plus, Search, Grid, List, X } from 'lucide-react';
import { useNotes } from '@hooks/useNotes';
import { NoteCard } from '@components/notes/NoteCard';
import { NoteEditor } from '@components/notes/NoteEditor';
import { Button } from '@components/shared/Button';
import { Input } from '@components/shared/Input';
import { LoadingSpinner } from '@components/shared/LoadingSpinner';
import type { Note } from '@types/*';
import './NotesPage.css';

type ViewMode = 'grid' | 'list';

export default function NotesPage() {
  const { notes, loading, error, createNote, updateNote, deleteNote } = useNotes();
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<Note | undefined>(undefined);
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);

  // Get all unique tags
  const allTags = useMemo(() => {
    const tagsSet = new Set<string>();
    notes.forEach((note) => {
      note.tags?.forEach((tag) => tagsSet.add(tag));
    });
    return Array.from(tagsSet).sort();
  }, [notes]);

  // Filter notes
  const filteredNotes = useMemo(() => {
    return notes.filter((note) => {
      const matchesSearch =
        searchQuery === '' ||
        note.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        note.body.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesTag =
        selectedTag === null || (note.tags && note.tags.includes(selectedTag));

      return matchesSearch && matchesTag;
    });
  }, [notes, searchQuery, selectedTag]);

  const handleCreateNote = () => {
    setEditingNote(undefined);
    setIsEditorOpen(true);
  };

  const handleEditNote = (note: Note) => {
    setEditingNote(note);
    setIsEditorOpen(true);
    setSelectedNoteId(null);
  };

  const handleSaveNote = async (data: any) => {
    if (editingNote) {
      await updateNote(editingNote.id, data);
    } else {
      await createNote(data);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    if (confirm('Are you sure you want to delete this note?')) {
      await deleteNote(noteId);
      setSelectedNoteId(null);
    }
  };

  const handleNoteClick = (noteId: string) => {
    setSelectedNoteId(noteId);
  };

  const selectedNote = selectedNoteId
    ? notes.find((n) => n.id === selectedNoteId)
    : null;

  if (loading) {
    return <LoadingSpinner fullScreen />;
  }

  if (error) {
    return (
      <div className="notes-error">
        <p>Error loading notes: {error}</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  // If a note is selected, show detail view
  if (selectedNote) {
    const NoteDetail = require('@components/notes/NoteDetail').NoteDetail;
    return (
      <NoteDetail
        note={selectedNote}
        onEdit={() => handleEditNote(selectedNote)}
        onDelete={() => handleDeleteNote(selectedNote.id)}
        onBack={() => setSelectedNoteId(null)}
      />
    );
  }

  return (
    <div className="notes-page">
      <div className="notes-header">
        <div className="notes-header-top">
          <h1 className="notes-title">Notes</h1>
          <Button onClick={handleCreateNote}>
            <Plus size={18} />
            New Note
          </Button>
        </div>

        <div className="notes-filters">
          <div className="notes-search">
            <Search className="notes-search-icon" size={18} />
            <input
              type="text"
              placeholder="Search notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="notes-search-input"
            />
          </div>

          <div className="notes-view-toggle">
            <button
              className={`notes-view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              aria-label="Grid view"
            >
              <Grid size={18} />
            </button>
            <button
              className={`notes-view-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')}
              aria-label="List view"
            >
              <List size={18} />
            </button>
          </div>
        </div>

        {allTags.length > 0 && (
          <div className="notes-tags-filter">
            <span className="notes-tags-filter-label">Filter by tag:</span>
            <div className="notes-tags-filter-list">
              {allTags.map((tag) => (
                <button
                  key={tag}
                  onClick={() =>
                    setSelectedTag(selectedTag === tag ? null : tag)
                  }
                  className={`notes-tag-filter ${
                    selectedTag === tag ? 'active' : ''
                  }`}
                >
                  {tag}
                  {selectedTag === tag && <X size={14} />}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {filteredNotes.length === 0 ? (
        <div className="notes-empty">
          {searchQuery || selectedTag ? (
            <>
              <p>No notes found matching your filters.</p>
              <Button
                variant="secondary"
                onClick={() => {
                  setSearchQuery('');
                  setSelectedTag(null);
                }}
              >
                Clear Filters
              </Button>
            </>
          ) : (
            <>
              <p>You don't have any notes yet.</p>
              <Button onClick={handleCreateNote}>
                <Plus size={18} />
                Create Your First Note
              </Button>
            </>
          )}
        </div>
      ) : (
        <div className={`notes-${viewMode}`}>
          {filteredNotes.map((note) => (
            <NoteCard
              key={note.id}
              note={note}
              onClick={() => handleNoteClick(note.id)}
            />
          ))}
        </div>
      )}

      <NoteEditor
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        onSave={handleSaveNote}
        note={editingNote}
        allTags={allTags}
      />
    </div>
  );
}

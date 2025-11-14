import { useState, useEffect } from 'react';
import { notesService } from '@services/notesService';
import type { Note, CreateNoteRequest } from '@types/*';

export function useNotes() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await notesService.getAll();
      setNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch notes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
  }, []);

  const createNote = async (data: CreateNoteRequest) => {
    const newNote = await notesService.create(data);
    setNotes((prev) => [newNote, ...prev]);
    return newNote;
  };

  const updateNote = async (id: string, data: Partial<CreateNoteRequest>) => {
    const updated = await notesService.update(id, data);
    setNotes((prev) => prev.map((n) => (n.id === id ? updated : n)));
    return updated;
  };

  const deleteNote = async (id: string) => {
    await notesService.delete(id);
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  return {
    notes,
    loading,
    error,
    createNote,
    updateNote,
    deleteNote,
    refetch: fetchNotes,
  };
}

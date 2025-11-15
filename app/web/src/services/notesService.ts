import { api } from './api';
import type { Note, CreateNoteRequest } from '@/types';

export const notesService = {
  getAll: async (): Promise<Note[]> => {
    const res = await api.get<any>('/notes');
    return Array.isArray(res) ? res as Note[] : (res?.data as Note[]) || [];
  },

  getById: (id: string) => api.get<Note>(`/notes/${id}`),

  create: async (data: CreateNoteRequest): Promise<Note> => {
    const res = await api.post<any>('/notes', data);
    return (res?.data as Note) || (res as Note);
  },

  update: async (id: string, data: Partial<CreateNoteRequest>): Promise<Note> => {
    const res = await api.patch<any>(`/notes/${id}`, data);
    return (res?.data as Note) || (res as Note);
  },

  delete: async (id: string): Promise<void> => {
    try {
      await api.delete<void>(`/notes/${id}`);
    } catch (e) {
      // Backend may not support delete yet; ignore to keep UI responsive
      console.warn('Delete note not supported, removing locally');
    }
  },
};

import { api } from './api';
import type { Note, CreateNoteRequest } from '@types/*';

export const notesService = {
  getAll: () => api.get<Note[]>('/notes'),

  getById: (id: string) => api.get<Note>(`/notes/${id}`),

  create: (data: CreateNoteRequest) => api.post<Note>('/notes', data),

  update: (id: string, data: Partial<CreateNoteRequest>) =>
    api.put<Note>(`/notes/${id}`, data),

  delete: (id: string) => api.delete<void>(`/notes/${id}`),
};

import { api } from './api';
import type { Reminder, CreateReminderRequest } from '@types/*';

export const remindersService = {
  getAll: () => api.get<Reminder[]>('/reminders'),

  create: async (data: CreateReminderRequest): Promise<Reminder> => {
    const res = await api.post<{success: boolean; data: Reminder}>('/reminders', data);
    return res.data;
  },

  snooze: (id: string, minutes: number) =>
    api.post<Reminder>(`/reminders/${id}/snooze`, { duration_minutes: minutes }),

  complete: (id: string) =>
    api.patch<Reminder>(`/reminders/${id}`, { status: 'completed' }),

  delete: (id: string) => api.delete<void>(`/reminders/${id}`),
};

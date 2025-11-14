import { api } from './api';
import type { Reminder, CreateReminderRequest } from '@types/*';

export const remindersService = {
  getAll: () => api.get<Reminder[]>('/reminders'),

  create: (data: CreateReminderRequest) =>
    api.post<Reminder>('/reminders', data),

  snooze: (id: string, minutes: number) =>
    api.post<Reminder>(`/reminders/${id}/snooze`, { duration_minutes: minutes }),

  complete: (id: string) =>
    api.post<Reminder>(`/reminders/${id}/complete`, {}),

  delete: (id: string) => api.delete<void>(`/reminders/${id}`),
};

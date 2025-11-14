import { api } from './api';
import type { CalendarEvent, CreateEventRequest } from '@types/*';

export const calendarService = {
  getEvents: (start: string, end: string) =>
    api.get<{ events: CalendarEvent[]; count: number }>(
      `/calendar/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
    ),

  create: (data: CreateEventRequest) =>
    api.post<CalendarEvent>('/calendar/events', data),

  delete: (id: string) => api.delete<void>(`/calendar/events/${id}`),
};

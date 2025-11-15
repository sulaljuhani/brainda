import { api } from './api';
import type { CalendarEvent, CreateEventRequest } from '@types/*';

export const calendarService = {
  getEvents: async (start: string, end: string): Promise<{ events: CalendarEvent[]; count: number }> => {
    const res = await api.get<any>(
      `/calendar/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
    );
    if (res?.events) return res as { events: CalendarEvent[]; count: number };
    const data = res?.data || {};
    return { events: (data.events as CalendarEvent[]) || [], count: (data.count as number) || 0 };
  },

  create: async (data: CreateEventRequest): Promise<CalendarEvent> => {
    const res = await api.post<any>('/calendar/events', data);
    // Backend returns {success: true, data: {...}} structure
    if (res?.data) {
      return res.data as CalendarEvent;
    }
    // Fallback for direct response
    return res as CalendarEvent;
  },

  delete: (id: string) => api.delete<void>(`/calendar/events/${id}`),
};

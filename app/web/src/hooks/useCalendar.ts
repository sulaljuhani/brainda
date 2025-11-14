import { useState, useEffect } from 'react';
import { calendarService } from '@services/calendarService';
import type { CalendarEvent, CreateEventRequest } from '@types/*';

export function useCalendar(start?: string, end?: string) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = async (startDate?: string, endDate?: string) => {
    try {
      setLoading(true);
      setError(null);

      // Default to current month if no dates provided
      const defaultStart = startDate || new Date().toISOString();
      const defaultEnd = endDate || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

      const response = await calendarService.getEvents(defaultStart, defaultEnd);
      setEvents(response.events);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents(start, end);
  }, [start, end]);

  const createEvent = async (data: CreateEventRequest) => {
    try {
      const newEvent = await calendarService.create(data);
      setEvents((prev) => [...prev, newEvent]);
      return newEvent;
    } catch (err) {
      console.error('Failed to create event:', err);
      throw err;
    }
  };

  const deleteEvent = async (id: string) => {
    await calendarService.delete(id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  return {
    events,
    loading,
    error,
    createEvent,
    deleteEvent,
    refetch: (startDate?: string, endDate?: string) => fetchEvents(startDate, endDate),
  };
}

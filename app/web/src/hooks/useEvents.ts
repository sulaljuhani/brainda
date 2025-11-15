import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@services/apiClient';
import type { CalendarEvent, CreateEventRequest } from '@types/*';

interface UseEventsOptions {
  categoryId?: string | null;
  status?: 'upcoming' | 'past' | 'all';
}

export function useEvents(options: UseEventsOptions = {}) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all events from past year to next year
      const pastYear = new Date();
      pastYear.setFullYear(pastYear.getFullYear() - 1);
      const futureYear = new Date();
      futureYear.setFullYear(futureYear.getFullYear() + 1);

      const params = new URLSearchParams({
        start: pastYear.toISOString(),
        end: futureYear.toISOString(),
      });

      const response = await apiClient.get<{
        success: boolean;
        data: { events: CalendarEvent[]; count: number };
      }>(`/calendar/events?${params.toString()}`);

      if (response.success && response.data) {
        let fetchedEvents = response.data.events;

        // Filter by category if specified
        if (options.categoryId !== undefined) {
          if (options.categoryId === null) {
            fetchedEvents = fetchedEvents.filter((e) => !e.category_id);
          } else {
            fetchedEvents = fetchedEvents.filter(
              (e) => e.category_id === options.categoryId
            );
          }
        }

        // Filter by status if specified
        const now = new Date().toISOString();
        if (options.status === 'upcoming') {
          fetchedEvents = fetchedEvents.filter((e) => e.starts_at >= now);
          // Sort ascending (soonest first)
          fetchedEvents.sort(
            (a, b) =>
              new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
          );
        } else if (options.status === 'past') {
          fetchedEvents = fetchedEvents.filter((e) => e.starts_at < now);
          // Sort descending (most recent first)
          fetchedEvents.sort(
            (a, b) =>
              new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime()
          );
          // Limit to last 20
          fetchedEvents = fetchedEvents.slice(0, 20);
        } else {
          // Sort by start date descending for 'all'
          fetchedEvents.sort(
            (a, b) =>
              new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime()
          );
        }

        setEvents(fetchedEvents);
      } else {
        throw new Error('Failed to fetch events');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch events';
      setError(errorMessage);
      console.error('Failed to fetch events:', err);
    } finally {
      setLoading(false);
    }
  }, [options.categoryId, options.status]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const createEvent = async (data: CreateEventRequest): Promise<CalendarEvent> => {
    try {
      const response = await apiClient.post<{
        success: boolean;
        data: CalendarEvent;
      }>('/calendar/events', data);

      if (response.success && response.data) {
        await fetchEvents();
        return response.data;
      }
      throw new Error('Failed to create event');
    } catch (err) {
      console.error('Failed to create event:', err);
      throw err;
    }
  };

  const updateEvent = async (
    id: string,
    data: Partial<CreateEventRequest>
  ): Promise<CalendarEvent> => {
    try {
      const response = await apiClient.patch<{
        success: boolean;
        data: CalendarEvent;
      }>(`/calendar/events/${id}`, data);

      if (response.success && response.data) {
        await fetchEvents();
        return response.data;
      }
      throw new Error('Failed to update event');
    } catch (err) {
      console.error('Failed to update event:', err);
      throw err;
    }
  };

  const deleteEvent = async (id: string): Promise<void> => {
    try {
      const response = await apiClient.delete<{ success: boolean }>(
        `/calendar/events/${id}`
      );

      if (response.success) {
        await fetchEvents();
      } else {
        throw new Error('Failed to delete event');
      }
    } catch (err) {
      console.error('Failed to delete event:', err);
      throw err;
    }
  };

  return {
    events,
    loading,
    error,
    createEvent,
    updateEvent,
    deleteEvent,
    refetch: fetchEvents,
  };
}

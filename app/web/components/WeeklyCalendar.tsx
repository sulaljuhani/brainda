'use client';

import { addWeeks, eachDayOfInterval, endOfWeek, format, isSameDay, startOfWeek } from 'date-fns';
import { useEffect, useMemo, useState } from 'react';

interface CalendarEvent {
  id: string;
  title: string;
  description?: string | null;
  starts_at: string;
  ends_at?: string | null;
  timezone: string;
  location_text?: string | null;
  rrule?: string | null;
  status: string;
  is_recurring_instance?: boolean;
}

interface CalendarResponse {
  success: boolean;
  data?: {
    events: CalendarEvent[];
    count: number;
  };
  error?: { message: string };
}

function formatDisplayTime(value: string) {
  const date = new Date(value);
  return format(date, 'HH:mm');
}

export default function WeeklyCalendar() {
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const weekStart = useMemo(() => startOfWeek(anchorDate, { weekStartsOn: 1 }), [anchorDate]);
  const weekEnd = useMemo(() => endOfWeek(anchorDate, { weekStartsOn: 1 }), [anchorDate]);
  const isoStart = useMemo(() => weekStart.toISOString(), [weekStart]);
  const isoEnd = useMemo(() => weekEnd.toISOString(), [weekEnd]);
  const days = useMemo(() => eachDayOfInterval({ start: weekStart, end: weekEnd }), [weekStart, weekEnd]);

  useEffect(() => {
    let isMounted = true;
    async function fetchEvents() {
      setLoading(true);
      setError(null);
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('api_token') : null;
        const response = await fetch(
          `/api/v1/calendar/events?start=${encodeURIComponent(isoStart)}&end=${encodeURIComponent(isoEnd)}`,
          {
            headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          }
        );
        if (!response.ok) {
          throw new Error(`Failed to load events (${response.status})`);
        }
        const payload = (await response.json()) as CalendarResponse;
        if (!payload.success) {
          throw new Error(payload.error?.message || 'Unable to load events');
        }
        if (isMounted) {
          setEvents(payload.data?.events ?? []);
        }
      } catch (err) {
        if (isMounted) {
          setEvents([]);
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchEvents();
    return () => {
      isMounted = false;
    };
  }, [isoStart, isoEnd]);

  return (
    <div className="weekly-calendar">
      <div className="calendar-header">
        <button onClick={() => setAnchorDate(addWeeks(weekStart, -1))} type="button">
          ← Previous
        </button>
        <h2>
          {format(weekStart, 'MMM d')} – {format(weekEnd, 'MMM d, yyyy')}
        </h2>
        <button onClick={() => setAnchorDate(addWeeks(weekStart, 1))} type="button">
          Next →
        </button>
      </div>

      {loading ? (
        <div className="calendar-loading">Loading calendar…</div>
      ) : error ? (
        <div className="calendar-error">{error}</div>
      ) : (
        <div className="calendar-grid">
          {days.map((day) => {
            const dayEvents = events.filter((event) => isSameDay(new Date(event.starts_at), day));

            return (
              <div key={day.toISOString()} className="calendar-day">
                <div className="day-header">{format(day, 'EEE d')}</div>
                <div className="day-events">
                  {dayEvents.length === 0 ? (
                    <div className="event empty">No events</div>
                  ) : (
                    dayEvents.map((event) => (
                      <div
                        key={`${event.id}-${event.starts_at}`}
                        className={`event ${event.is_recurring_instance ? 'recurring' : ''}`}
                      >
                        <div className="event-time">{formatDisplayTime(event.starts_at)}</div>
                        <div className="event-title">{event.title}</div>
                        {event.location_text ? (
                          <div className="event-location">📍 {event.location_text}</div>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

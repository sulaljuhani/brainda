import { useState, useMemo, useRef, useEffect } from 'react';
import {
  format,
  addMonths,
  subMonths,
  addWeeks,
  subWeeks,
  startOfMonth,
  endOfMonth,
} from 'date-fns';
import { useCalendar } from '@hooks/useCalendar';
import { WeeklyCalendar } from '@components/calendar/WeeklyCalendar';
import { MonthlyCalendar } from '@components/calendar/MonthlyCalendar';
import { EventForm } from '@components/calendar/EventForm';
import { GoogleCalendarConnect } from '@components/calendar/GoogleCalendarConnect';
import type { CalendarEvent, CreateEventRequest } from '@types/*';
import styles from './CalendarPage.module.css';

type CalendarView = 'week' | 'month';

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<CalendarView>('week');
  const [isEventFormOpen, setIsEventFormOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(
    null
  );
  const [showCreateDropdown, setShowCreateDropdown] = useState(false);
  const [showOneTimeEvents, setShowOneTimeEvents] = useState(true);
  const [showRecurringEvents, setShowRecurringEvents] = useState(true);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Calculate date range for fetching events
  const dateRange = useMemo(() => {
    if (view === 'week') {
      const start = new Date(currentDate);
      start.setDate(currentDate.getDate() - 7);
      const end = new Date(currentDate);
      end.setDate(currentDate.getDate() + 14);
      return {
        start: start.toISOString(),
        end: end.toISOString(),
      };
    } else {
      const start = startOfMonth(currentDate);
      start.setDate(start.getDate() - 7);
      const end = endOfMonth(currentDate);
      end.setDate(end.getDate() + 7);
      return {
        start: start.toISOString(),
        end: end.toISOString(),
      };
    }
  }, [currentDate, view]);

  const { events, loading, error, createEvent, deleteEvent, refetch } =
    useCalendar(dateRange.start, dateRange.end);

  // Filter events based on selected filters
  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const isRecurring = Boolean(event.rrule);
      if (isRecurring && !showRecurringEvents) return false;
      if (!isRecurring && !showOneTimeEvents) return false;
      return true;
    });
  }, [events, showOneTimeEvents, showRecurringEvents]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowCreateDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handlePrevious = () => {
    if (view === 'week') {
      setCurrentDate((prev) => subWeeks(prev, 1));
    } else {
      setCurrentDate((prev) => subMonths(prev, 1));
    }
  };

  const handleNext = () => {
    if (view === 'week') {
      setCurrentDate((prev) => addWeeks(prev, 1));
    } else {
      setCurrentDate((prev) => addMonths(prev, 1));
    }
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  const handleCreateEvent = () => {
    setSelectedEvent(null);
    setSelectedDate(undefined);
    setIsEventFormOpen(true);
    setShowCreateDropdown(false);
  };

  const handleCreateOneTimeTask = () => {
    // For now, this opens the same event form
    // In the future, this could open a task-specific form
    handleCreateEvent();
  };

  const handleCreateRecurringTask = () => {
    // For now, this opens the event form with recurring enabled
    // You could preset isRecurring to true
    handleCreateEvent();
  };

  const handleDayClick = (date: Date) => {
    setSelectedDate(date);
    setSelectedEvent(null);
    setIsEventFormOpen(true);
  };

  const handleEventClick = (event: CalendarEvent) => {
    setSelectedEvent(event);
    setIsEventFormOpen(true);
  };

  const handleEventSubmit = async (data: CreateEventRequest) => {
    await createEvent(data);
    setIsEventFormOpen(false);
    setSelectedEvent(null);
    setSelectedDate(undefined);
  };

  const handleEventDelete = async (eventId: string) => {
    await deleteEvent(eventId);
  };

  const formatHeaderDate = () => {
    if (view === 'week') {
      return format(currentDate, 'MMMM yyyy');
    } else {
      return format(currentDate, 'MMMM yyyy');
    }
  };

  return (
    <div className={styles.calendarPage}>
      {/* Google Calendar Integration */}
      <GoogleCalendarConnect />

      {/* Calendar Header */}
      <div className={styles.calendarHeader}>
        <div className={styles.calendarTitle}>
          <h1>{formatHeaderDate()}</h1>
        </div>

        <div className={styles.calendarControls}>
          <div className={styles.viewToggle}>
            <button
              className={`${styles.viewToggleBtn} ${
                view === 'week' ? styles.viewToggleBtnActive : ''
              }`}
              onClick={() => setView('week')}
            >
              Week
            </button>
            <button
              className={`${styles.viewToggleBtn} ${
                view === 'month' ? styles.viewToggleBtnActive : ''
              }`}
              onClick={() => setView('month')}
            >
              Month
            </button>
          </div>

          <div className={styles.navigationControls}>
            <button
              className={styles.navBtn}
              onClick={handlePrevious}
              aria-label="Previous"
            >
              ‹
            </button>
            <button className={styles.todayBtn} onClick={handleToday}>
              Today
            </button>
            <button
              className={styles.navBtn}
              onClick={handleNext}
              aria-label="Next"
            >
              ›
            </button>
          </div>

          <div className={styles.createBtnContainer} ref={dropdownRef}>
            <button
              className={styles.createEventBtn}
              onClick={() => setShowCreateDropdown(!showCreateDropdown)}
            >
              + New Item
            </button>

            {showCreateDropdown && (
              <div className={styles.createDropdown}>
                <button
                  className={styles.dropdownItem}
                  onClick={handleCreateEvent}
                >
                  Event
                </button>
                <button
                  className={styles.dropdownItem}
                  onClick={handleCreateRecurringTask}
                >
                  Recurring Task
                </button>
                <button
                  className={styles.dropdownItem}
                  onClick={handleCreateOneTimeTask}
                >
                  One-Time Task
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Filters */}
        <div className={styles.calendarFilters}>
          <button
            className={`${styles.filterBtn} ${showOneTimeEvents ? styles.filterBtnActive : ''}`}
            onClick={() => setShowOneTimeEvents(!showOneTimeEvents)}
          >
            One-Time Events
          </button>
          <button
            className={`${styles.filterBtn} ${showRecurringEvents ? styles.filterBtnActive : ''}`}
            onClick={() => setShowRecurringEvents(!showRecurringEvents)}
          >
            Recurring Tasks
          </button>
        </div>
      </div>

      {/* Loading/Error States */}
      {loading && (
        <div className={styles.loadingContainer}>
          <div className={styles.loadingSpinner}>Loading events...</div>
        </div>
      )}

      {error && (
        <div className={styles.errorContainer}>
          <p>Error loading events: {error}</p>
          <button
            className={styles.retryBtn}
            onClick={() => refetch(dateRange.start, dateRange.end)}
          >
            Retry
          </button>
        </div>
      )}

      {/* Calendar Views */}
      {!loading && !error && (
        <div className={styles.calendarContent}>
          {view === 'week' ? (
            <WeeklyCalendar
              currentDate={currentDate}
              events={filteredEvents}
              onEventClick={handleEventClick}
              onEventDelete={handleEventDelete}
              onDayClick={handleDayClick}
            />
          ) : (
            <MonthlyCalendar
              currentDate={currentDate}
              events={filteredEvents}
              onEventClick={handleEventClick}
              onDayClick={handleDayClick}
            />
          )}
        </div>
      )}

      {/* Event Form Modal */}
      <EventForm
        isOpen={isEventFormOpen}
        onClose={() => {
          setIsEventFormOpen(false);
          setSelectedEvent(null);
          setSelectedDate(undefined);
        }}
        onSubmit={handleEventSubmit}
        initialDate={selectedDate}
        event={selectedEvent}
      />
    </div>
  );
}

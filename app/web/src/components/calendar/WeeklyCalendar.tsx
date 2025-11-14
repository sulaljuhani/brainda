import { useMemo } from 'react';
import {
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameDay,
  format,
  isToday,
} from 'date-fns';
import type { CalendarEvent } from '@types/*';
import { EventCard } from './EventCard';
import styles from './calendar.module.css';

interface WeeklyCalendarProps {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onEventDelete?: (eventId: string) => void;
  onDayClick?: (date: Date) => void;
}

export function WeeklyCalendar({
  currentDate,
  events,
  onEventClick,
  onEventDelete,
  onDayClick,
}: WeeklyCalendarProps) {
  const weekDays = useMemo(() => {
    const start = startOfWeek(currentDate, { weekStartsOn: 0 }); // Sunday
    const end = endOfWeek(currentDate, { weekStartsOn: 0 });
    return eachDayOfInterval({ start, end });
  }, [currentDate]);

  const getEventsForDay = (day: Date) => {
    return events.filter((event) => {
      const eventDate = new Date(event.starts_at);
      return isSameDay(eventDate, day);
    });
  };

  return (
    <div className={styles.weeklyCalendar}>
      <div className={styles.weekGrid}>
        {weekDays.map((day) => {
          const dayEvents = getEventsForDay(day);
          const isDayToday = isToday(day);

          return (
            <div
              key={day.toISOString()}
              className={`${styles.weekDay} ${
                isDayToday ? styles.weekDayToday : ''
              }`}
              onClick={() => onDayClick?.(day)}
            >
              <div className={styles.weekDayHeader}>
                <div className={styles.weekDayName}>
                  {format(day, 'EEE')}
                </div>
                <div
                  className={`${styles.weekDayNumber} ${
                    isDayToday ? styles.weekDayNumberToday : ''
                  }`}
                >
                  {format(day, 'd')}
                </div>
              </div>

              <div className={styles.weekDayEvents}>
                {dayEvents.length === 0 ? (
                  <div className={styles.noEvents}>No events</div>
                ) : (
                  dayEvents.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      onClick={() => onEventClick?.(event)}
                      onDelete={() => onEventDelete?.(event.id)}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

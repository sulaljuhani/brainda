import { useMemo } from 'react';
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameDay,
  isSameMonth,
  format,
  isToday,
} from 'date-fns';
import type { CalendarEvent } from '@types/*';
import styles from './calendar.module.css';

interface MonthlyCalendarProps {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onDayClick?: (date: Date) => void;
}

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function MonthlyCalendar({
  currentDate,
  events,
  onEventClick,
  onDayClick,
}: MonthlyCalendarProps) {
  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(currentDate);
    const monthEnd = endOfMonth(currentDate);
    const calendarStart = startOfWeek(monthStart, { weekStartsOn: 0 });
    const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 0 });

    return eachDayOfInterval({ start: calendarStart, end: calendarEnd });
  }, [currentDate]);

  const getEventsForDay = (day: Date) => {
    return events.filter((event) => {
      const eventDate = new Date(event.starts_at);
      return isSameDay(eventDate, day);
    });
  };

  return (
    <div className={styles.monthlyCalendar}>
      {/* Weekday headers */}
      <div className={styles.monthGrid}>
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className={styles.monthWeekdayHeader}>
            {label}
          </div>
        ))}

        {/* Calendar days */}
        {calendarDays.map((day) => {
          const dayEvents = getEventsForDay(day);
          const isDayInCurrentMonth = isSameMonth(day, currentDate);
          const isDayToday = isToday(day);

          return (
            <div
              key={day.toISOString()}
              className={`${styles.monthDay} ${
                !isDayInCurrentMonth ? styles.monthDayOutside : ''
              } ${isDayToday ? styles.monthDayToday : ''}`}
              onClick={() => isDayInCurrentMonth && onDayClick?.(day)}
            >
              <div className={styles.monthDayNumber}>
                {format(day, 'd')}
              </div>

              <div className={styles.monthDayEvents}>
                {dayEvents.slice(0, 3).map((event) => (
                  <div
                    key={event.id}
                    className={styles.monthEvent}
                    onClick={(e) => {
                      e.stopPropagation();
                      onEventClick?.(event);
                    }}
                    title={`${event.title}${
                      event.description ? `\n${event.description}` : ''
                    }`}
                  >
                    <span className={styles.monthEventTime}>
                      {format(new Date(event.starts_at), 'h:mm a')}
                    </span>
                    <span className={styles.monthEventTitle}>
                      {event.title}
                      {event.is_recurring_instance && ' ↻'}
                    </span>
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className={styles.monthEventMore}>
                    +{dayEvents.length - 3} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

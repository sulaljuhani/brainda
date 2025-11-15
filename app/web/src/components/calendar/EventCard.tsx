import type { CalendarEvent } from '@/types';
import styles from './calendar.module.css';

interface EventCardProps {
  event: CalendarEvent;
  onClick?: () => void;
  onDelete?: () => void;
}

export function EventCard({ event, onClick, onDelete }: EventCardProps) {
  const startTime = new Date(event.starts_at);
  const endTime = event.ends_at ? new Date(event.ends_at) : null;

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete && confirm('Delete this event?')) {
      onDelete();
    }
  };

  return (
    <div className={styles.eventCard} onClick={onClick}>
      <div className={styles.eventCardHeader}>
        <div className={styles.eventCardTime}>
          {formatTime(startTime)}
          {endTime && ` - ${formatTime(endTime)}`}
        </div>
        {event.is_recurring_instance && (
          <span className={styles.recurringBadge} title="Recurring event">
            ↻
          </span>
        )}
      </div>

      <div className={styles.eventCardTitle}>{event.title}</div>

      {event.description && (
        <div className={styles.eventCardDescription}>{event.description}</div>
      )}

      {event.location_text && (
        <div className={styles.eventCardLocation}>
          📍 {event.location_text}
        </div>
      )}

      <div className={styles.eventCardActions}>
        <button
          className={styles.eventCardDeleteBtn}
          onClick={handleDelete}
          title="Delete event"
        >
          ×
        </button>
      </div>
    </div>
  );
}

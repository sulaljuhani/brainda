import { formatDistanceToNow } from 'date-fns';
import { Clock, Repeat, CheckCircle, Bell } from 'lucide-react';
import type { Reminder } from '../../types/api';
import styles from './ReminderItem.module.css';

interface ReminderItemProps {
  reminder: Reminder;
  onSnooze: (id: string, minutes: number) => void;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ReminderItem({ reminder, onSnooze, onComplete, onDelete }: ReminderItemProps) {
  const isPastDue = new Date(reminder.due_at_utc) < new Date();
  const isActive = reminder.status === 'active';
  const isSnoozed = reminder.status === 'snoozed';
  const isCompleted = reminder.status === 'completed';

  const handleSnooze = (e: React.MouseEvent, minutes: number) => {
    e.stopPropagation();
    onSnooze(reminder.id, minutes);
  };

  const handleComplete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onComplete(reminder.id);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this reminder?')) {
      onDelete(reminder.id);
    }
  };

  return (
    <div className={`${styles.reminderItem} ${isCompleted ? styles.completed : ''} ${isPastDue && isActive ? styles.overdue : ''}`}>
      <div className={styles.reminderHeader}>
        <div className={styles.reminderInfo}>
          <h3 className={styles.reminderTitle}>{reminder.title}</h3>
          {reminder.body && (
            <p className={styles.reminderBody}>{reminder.body}</p>
          )}

          <div className={styles.reminderMeta}>
            <span className={styles.reminderTime}>
              <Clock size={14} />
              {formatDistanceToNow(new Date(reminder.due_at_utc), { addSuffix: true })}
            </span>

            {reminder.repeat_rrule && (
              <span className={styles.recurringBadge}>
                <Repeat size={14} />
                Recurring
              </span>
            )}

            {isSnoozed && (
              <span className={styles.snoozedBadge}>
                <Bell size={14} />
                Snoozed
              </span>
            )}
          </div>
        </div>

        <div className={styles.reminderActions}>
          {(isActive || isSnoozed) && (
            <>
              <div className={styles.snoozeGroup}>
                <button
                  onClick={(e) => handleSnooze(e, 15)}
                  className={styles.snoozeBtn}
                  title="Snooze for 15 minutes"
                >
                  15m
                </button>
                <button
                  onClick={(e) => handleSnooze(e, 60)}
                  className={styles.snoozeBtn}
                  title="Snooze for 1 hour"
                >
                  1h
                </button>
                <button
                  onClick={(e) => handleSnooze(e, 1440)}
                  className={styles.snoozeBtn}
                  title="Snooze for 1 day"
                >
                  1d
                </button>
              </div>

              <button
                onClick={handleComplete}
                className={styles.completeBtn}
                title="Mark as complete"
              >
                <CheckCircle size={18} />
                Complete
              </button>
            </>
          )}

          <button
            onClick={handleDelete}
            className={styles.deleteBtn}
            title="Delete reminder"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

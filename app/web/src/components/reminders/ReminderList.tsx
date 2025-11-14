import { ReminderItem } from './ReminderItem';
import type { Reminder } from '../../types/api';
import styles from './ReminderList.module.css';

interface ReminderListProps {
  reminders: Reminder[];
  onSnooze: (id: string, minutes: number) => void;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
  emptyMessage?: string;
}

export function ReminderList({
  reminders,
  onSnooze,
  onComplete,
  onDelete,
  emptyMessage = 'No reminders found',
}: ReminderListProps) {
  if (reminders.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyMessage}>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={styles.reminderList}>
      {reminders.map((reminder) => (
        <ReminderItem
          key={reminder.id}
          reminder={reminder}
          onSnooze={onSnooze}
          onComplete={onComplete}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { Modal } from '@components/shared/Modal';
import { CategoryPicker } from '@components/shared/CategoryPicker';
import { RecurrenceInput } from '@components/shared/RecurrenceInput';
import { CategoryManager } from '@components/shared/CategoryManager';
import { useTasks } from '@hooks/useTasks';
import { useEvents } from '@hooks/useEvents';
import type { Reminder, CreateReminderRequest } from '@/types';
import styles from './ReminderForm.module.css';

interface ReminderFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateReminderRequest) => Promise<void>;
  reminder?: Reminder | null;
}

export function ReminderForm({
  isOpen,
  onClose,
  onSubmit,
  reminder,
}: ReminderFormProps) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [dueAtUtc, setDueAtUtc] = useState('');
  const [dueAtLocal, setDueAtLocal] = useState('');
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [repeatRrule, setRepeatRrule] = useState('');
  const [linkType, setLinkType] = useState<'none' | 'task' | 'event'>('none');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [calendarEventId, setCalendarEventId] = useState<string | null>(null);
  const [offsetDays, setOffsetDays] = useState<number>(0);
  const [offsetType, setOffsetType] = useState<'before' | 'after'>('before');
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch tasks and events for linking dropdowns
  const { tasks } = useTasks({ status: 'active' });
  const { events } = useEvents({ status: 'all' });

  // Reset form when opening
  useEffect(() => {
    if (isOpen) {
      if (reminder) {
        setTitle(reminder.title);
        setBody(reminder.body || '');
        setCategoryId(reminder.category_id || null);
        setDueAtUtc(reminder.due_at_utc || '');
        setRepeatRrule(reminder.repeat_rrule || '');

        // Set link type based on what's linked
        if (reminder.task_id) {
          setLinkType('task');
          setTaskId(reminder.task_id);
          setCalendarEventId(null);
        } else if (reminder.calendar_event_id) {
          setLinkType('event');
          setCalendarEventId(reminder.calendar_event_id);
          setTaskId(null);
        } else {
          setLinkType('none');
          setTaskId(null);
          setCalendarEventId(null);
        }

        setOffsetDays(reminder.offset_days || 0);
        setOffsetType(reminder.offset_type || 'before');
      } else {
        setTitle('');
        setBody('');
        setCategoryId(null);
        setDueAtUtc('');
        setRepeatRrule('');
        setLinkType('none');
        setTaskId(null);
        setCalendarEventId(null);
        setOffsetDays(0);
        setOffsetType('before');
      }
    }
  }, [isOpen, reminder]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      alert('Please enter a reminder title');
      return;
    }

    // Validation for linked reminders
    if (linkType !== 'none' && (!offsetDays || offsetDays < 0)) {
      alert('Please enter a valid offset (number of days)');
      return;
    }

    setIsSubmitting(true);
    try {
      const data: CreateReminderRequest = {
        title: title.trim(),
        body: body.trim() || undefined,
        category_id: categoryId || undefined,
        due_at_utc: dueAtUtc!,
        due_at_local: dueAtLocal!,
        timezone: timezone,
        repeat_rrule: repeatRrule || undefined,
        task_id: linkType === 'task' ? taskId || undefined : undefined,
        calendar_event_id: linkType === 'event' ? calendarEventId || undefined : undefined,
        offset_days: linkType !== 'none' ? offsetDays : undefined,
        offset_type: linkType !== 'none' ? offsetType : undefined,
      };

      await onSubmit(data);
      onClose();
    } catch (err) {
      console.error('Failed to create reminder:', err);
      alert('Failed to create reminder. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={reminder ? 'Edit Reminder' : 'Create Reminder'}
      >
        <form onSubmit={handleSubmit} className={styles.reminderForm}>
          <div className={styles.formGroup}>
            <label className={styles.label}>
              Reminder Title<span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              className={styles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What do you want to be reminded about?"
              required
              autoFocus
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Notes</label>
            <textarea
              className={styles.textarea}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Additional details (optional)"
              rows={3}
            />
          </div>

          <CategoryPicker
            type="reminders"
            value={categoryId}
            onChange={setCategoryId}
            onManageCategories={() => setShowCategoryManager(true)}
          />

          <div className={styles.formGroup}>
            <label className={styles.label}>Link to Task or Event</label>
            <select
              className={styles.select}
              value={linkType}
              onChange={(e) => {
                const newLinkType = e.target.value as 'none' | 'task' | 'event';
                setLinkType(newLinkType);
                if (newLinkType === 'none') {
                  setTaskId(null);
                  setCalendarEventId(null);
                }
              }}
            >
              <option value="none">None (standalone reminder)</option>
              <option value="task">Link to Task</option>
              <option value="event">Link to Event</option>
            </select>
          </div>

          {linkType === 'task' && (
            <>
              <div className={styles.formGroup}>
                <label className={styles.label}>Select Task</label>
                <select
                  className={styles.select}
                  value={taskId || ''}
                  onChange={(e) => setTaskId(e.target.value || null)}
                >
                  <option value="">-- Select a task --</option>
                  {tasks.map((task) => (
                    <option key={task.id} value={task.id}>
                      {task.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Offset (days)</label>
                  <input
                    type="number"
                    className={styles.input}
                    value={offsetDays}
                    onChange={(e) => setOffsetDays(parseInt(e.target.value) || 0)}
                    min="0"
                    placeholder="0"
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label}>When</label>
                  <select
                    className={styles.select}
                    value={offsetType}
                    onChange={(e) => setOffsetType(e.target.value as 'before' | 'after')}
                  >
                    <option value="before">Before task</option>
                    <option value="after">After task</option>
                  </select>
                </div>
              </div>

              <div className={styles.infoNote}>
                Reminder will fire {offsetDays} day{offsetDays !== 1 ? 's' : ''} {offsetType} the task's start date
              </div>
            </>
          )}

          {linkType === 'event' && (
            <>
              <div className={styles.formGroup}>
                <label className={styles.label}>Select Event</label>
                <select
                  className={styles.select}
                  value={calendarEventId || ''}
                  onChange={(e) => setCalendarEventId(e.target.value || null)}
                >
                  <option value="">-- Select an event --</option>
                  {events.map((event) => (
                    <option key={event.id} value={event.id}>
                      {event.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.label}>Offset (days)</label>
                  <input
                    type="number"
                    className={styles.input}
                    value={offsetDays}
                    onChange={(e) => setOffsetDays(parseInt(e.target.value) || 0)}
                    min="0"
                    placeholder="0"
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label}>When</label>
                  <select
                    className={styles.select}
                    value={offsetType}
                    onChange={(e) => setOffsetType(e.target.value as 'before' | 'after')}
                  >
                    <option value="before">Before event</option>
                    <option value="after">After event</option>
                  </select>
                </div>
              </div>

              <div className={styles.infoNote}>
                Reminder will fire {offsetDays} day{offsetDays !== 1 ? 's' : ''} {offsetType} the event's start time
              </div>
            </>
          )}

          {linkType === 'none' && (
            <>
              <div className={styles.formGroup}>
                <label className={styles.label}>Due Date & Time</label>
                <input
                  type="datetime-local"
                  className={styles.input}
                  value={dueAtUtc}
                  onChange={(e) => {
                    setDueAtUtc(e.target.value);
                    setDueAtLocal(e.target.value);
                  }}
                  placeholder="When should the reminder fire?"
                />
              </div>

              <RecurrenceInput
                type="reminder"
                value={repeatRrule}
                onChange={setRepeatRrule}
              />
            </>
          )}

          <div className={styles.formActions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting
                ? 'Saving...'
                : reminder
                ? 'Update Reminder'
                : 'Create Reminder'}
            </button>
          </div>
        </form>
      </Modal>

      <CategoryManager
        isOpen={showCategoryManager}
        onClose={() => setShowCategoryManager(false)}
        type="reminders"
      />
    </>
  );
}

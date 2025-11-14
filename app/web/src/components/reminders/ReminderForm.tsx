import { useState } from 'react';
import { RRule, Frequency } from 'rrule';
import { X, Calendar, Repeat } from 'lucide-react';
import type { CreateReminderRequest } from '../../types/api';
import styles from './ReminderForm.module.css';

interface ReminderFormProps {
  onSubmit: (data: CreateReminderRequest) => Promise<void>;
  onCancel: () => void;
}

export function ReminderForm({ onSubmit, onCancel }: ReminderFormProps) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [isRecurring, setIsRecurring] = useState(false);
  const [frequency, setFrequency] = useState<Frequency>(RRule.DAILY);
  const [interval, setInterval] = useState(1);
  const [count, setCount] = useState<number | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    if (!dueDate) {
      setError('Due date is required');
      return;
    }

    try {
      setSubmitting(true);

      // Combine date and time
      const dateTimeStr = dueTime
        ? `${dueDate}T${dueTime}:00Z`
        : `${dueDate}T12:00:00Z`;

      const dueAtUtc = new Date(dateTimeStr).toISOString();

      let rruleString: string | undefined;
      if (isRecurring) {
        const dtstart = new Date(dateTimeStr);
        const rruleOptions: any = {
          freq: frequency,
          interval,
          dtstart,
        };

        if (count) {
          rruleOptions.count = count;
        }

        const rrule = new RRule(rruleOptions);
        rruleString = rrule.toString();
      }

      const data: CreateReminderRequest = {
        title: title.trim(),
        body: body.trim() || undefined,
        due_at_utc: dueAtUtc,
        repeat_rrule: rruleString,
      };

      await onSubmit(data);

      // Reset form
      setTitle('');
      setBody('');
      setDueDate('');
      setDueTime('');
      setIsRecurring(false);
      setFrequency(RRule.DAILY);
      setInterval(1);
      setCount(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create reminder');
    } finally {
      setSubmitting(false);
    }
  };

  const frequencyOptions = [
    { value: RRule.DAILY, label: 'Daily' },
    { value: RRule.WEEKLY, label: 'Weekly' },
    { value: RRule.MONTHLY, label: 'Monthly' },
    { value: RRule.YEARLY, label: 'Yearly' },
  ];

  return (
    <div className={styles.formOverlay} onClick={onCancel}>
      <div className={styles.formContainer} onClick={(e) => e.stopPropagation()}>
        <div className={styles.formHeader}>
          <h2 className={styles.formTitle}>New Reminder</h2>
          <button onClick={onCancel} className={styles.closeBtn} aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && (
            <div className={styles.error}>{error}</div>
          )}

          <div className={styles.formGroup}>
            <label htmlFor="title" className={styles.label}>
              Title *
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className={styles.input}
              placeholder="What do you want to be reminded about?"
              required
              autoFocus
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="body" className={styles.label}>
              Notes
            </label>
            <textarea
              id="body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className={styles.textarea}
              placeholder="Additional details (optional)"
              rows={3}
            />
          </div>

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label htmlFor="dueDate" className={styles.label}>
                <Calendar size={16} />
                Due Date *
              </label>
              <input
                id="dueDate"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className={styles.input}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="dueTime" className={styles.label}>
                Time
              </label>
              <input
                id="dueTime"
                type="time"
                value={dueTime}
                onChange={(e) => setDueTime(e.target.value)}
                className={styles.input}
              />
            </div>
          </div>

          <div className={styles.recurringSection}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={isRecurring}
                onChange={(e) => setIsRecurring(e.target.checked)}
                className={styles.checkbox}
              />
              <Repeat size={16} />
              Make this recurring
            </label>

            {isRecurring && (
              <div className={styles.recurringOptions}>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label htmlFor="frequency" className={styles.label}>
                      Frequency
                    </label>
                    <select
                      id="frequency"
                      value={frequency}
                      onChange={(e) => setFrequency(Number(e.target.value) as Frequency)}
                      className={styles.select}
                    >
                      {frequencyOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label htmlFor="interval" className={styles.label}>
                      Every
                    </label>
                    <input
                      id="interval"
                      type="number"
                      min="1"
                      value={interval}
                      onChange={(e) => setInterval(Number(e.target.value))}
                      className={styles.input}
                    />
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label htmlFor="count" className={styles.label}>
                    Number of occurrences (optional)
                  </label>
                  <input
                    id="count"
                    type="number"
                    min="1"
                    value={count || ''}
                    onChange={(e) => setCount(e.target.value ? Number(e.target.value) : undefined)}
                    className={styles.input}
                    placeholder="Leave empty for infinite"
                  />
                </div>

                <div className={styles.rrulePreview}>
                  <strong>Summary:</strong> Repeats{' '}
                  {interval > 1 ? `every ${interval} ` : ''}
                  {frequencyOptions.find((f) => f.value === frequency)?.label.toLowerCase()}
                  {count ? ` for ${count} occurrences` : ''}
                </div>
              </div>
            )}
          </div>

          <div className={styles.formActions}>
            <button
              type="button"
              onClick={onCancel}
              className={styles.cancelBtn}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create Reminder'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

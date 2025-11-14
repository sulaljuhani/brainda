import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { RRule } from 'rrule';
import type { CreateEventRequest, CalendarEvent } from '@types/*';
import styles from './calendar.module.css';

interface EventFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateEventRequest) => Promise<void>;
  initialDate?: Date;
  event?: CalendarEvent | null;
}

export function EventForm({
  isOpen,
  onClose,
  onSubmit,
  initialDate,
  event,
}: EventFormProps) {
  const [formData, setFormData] = useState<CreateEventRequest>({
    title: '',
    description: '',
    starts_at: '',
    ends_at: '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    location_text: '',
    rrule: '',
  });

  const [isRecurring, setIsRecurring] = useState(false);
  const [recurringPattern, setRecurringPattern] = useState('DAILY');
  const [recurringInterval, setRecurringInterval] = useState('1');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (event) {
      setFormData({
        title: event.title,
        description: event.description || '',
        starts_at: event.starts_at,
        ends_at: event.ends_at || '',
        timezone: event.timezone,
        location_text: event.location_text || '',
        rrule: event.rrule || '',
      });
      setIsRecurring(!!event.rrule);
    } else if (initialDate) {
      const dateStr = format(initialDate, "yyyy-MM-dd'T'HH:mm");
      setFormData((prev) => ({
        ...prev,
        starts_at: dateStr,
      }));
    }
  }, [event, initialDate]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const generateRRule = () => {
    if (!isRecurring) return '';

    const freq = recurringPattern as 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY';
    const interval = parseInt(recurringInterval) || 1;

    const rule = new RRule({
      freq: RRule[freq],
      interval,
    });

    return rule.toString();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const submitData = {
        ...formData,
        rrule: isRecurring ? generateRRule() : undefined,
      };

      await onSubmit(submitData);
      onClose();
      resetForm();
    } catch (error) {
      console.error('Failed to submit event:', error);
      alert('Failed to create event. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      title: '',
      description: '',
      starts_at: '',
      ends_at: '',
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      location_text: '',
      rrule: '',
    });
    setIsRecurring(false);
    setRecurringPattern('DAILY');
    setRecurringInterval('1');
  };

  const handleClose = () => {
    onClose();
    resetForm();
  };

  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={handleClose}>
      <div
        className={styles.modalContent}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.modalHeader}>
          <h2>{event ? 'Edit Event' : 'Create Event'}</h2>
          <button
            className={styles.modalCloseBtn}
            onClick={handleClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.eventForm}>
          <div className={styles.formGroup}>
            <label htmlFor="title">
              Title <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              id="title"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
              placeholder="Event title"
              className={styles.input}
            />
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Event description (optional)"
              className={styles.textarea}
              rows={3}
            />
          </div>

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label htmlFor="starts_at">
                Start Time <span className={styles.required}>*</span>
              </label>
              <input
                type="datetime-local"
                id="starts_at"
                name="starts_at"
                value={formData.starts_at}
                onChange={handleChange}
                required
                className={styles.input}
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="ends_at">End Time</label>
              <input
                type="datetime-local"
                id="ends_at"
                name="ends_at"
                value={formData.ends_at}
                onChange={handleChange}
                className={styles.input}
              />
            </div>
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="location_text">Location</label>
            <input
              type="text"
              id="location_text"
              name="location_text"
              value={formData.location_text}
              onChange={handleChange}
              placeholder="Event location (optional)"
              className={styles.input}
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={isRecurring}
                onChange={(e) => setIsRecurring(e.target.checked)}
              />
              <span>Recurring event</span>
            </label>
          </div>

          {isRecurring && (
            <div className={styles.recurringOptions}>
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label htmlFor="recurringPattern">Repeat</label>
                  <select
                    id="recurringPattern"
                    value={recurringPattern}
                    onChange={(e) => setRecurringPattern(e.target.value)}
                    className={styles.select}
                  >
                    <option value="DAILY">Daily</option>
                    <option value="WEEKLY">Weekly</option>
                    <option value="MONTHLY">Monthly</option>
                    <option value="YEARLY">Yearly</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label htmlFor="recurringInterval">Every</label>
                  <input
                    type="number"
                    id="recurringInterval"
                    value={recurringInterval}
                    onChange={(e) => setRecurringInterval(e.target.value)}
                    min="1"
                    className={styles.input}
                  />
                </div>
              </div>
            </div>
          )}

          <div className={styles.formActions}>
            <button
              type="button"
              onClick={handleClose}
              className={styles.btnSecondary}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.btnPrimary}
              disabled={submitting}
            >
              {submitting ? 'Saving...' : event ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

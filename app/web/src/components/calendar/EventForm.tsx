import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { Modal } from '@components/shared/Modal';
import { CategoryPicker } from '@components/shared/CategoryPicker';
import { RecurrenceInput } from '@components/shared/RecurrenceInput';
import { CategoryManager } from '@components/shared/CategoryManager';
import type { CreateEventRequest, CalendarEvent } from '@types/*';
import styles from './EventForm.module.css';

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
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [startDate, setStartDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endDate, setEndDate] = useState('');
  const [endTime, setEndTime] = useState('');
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone
  );
  const [locationText, setLocationText] = useState('');
  const [rrule, setRrule] = useState('');
  const [showCategoryManager, setShowCategoryManager] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form when opening
  useEffect(() => {
    if (isOpen) {
      if (event) {
        // Parse existing event datetime
        const startsAt = new Date(event.starts_at);
        setStartDate(format(startsAt, 'yyyy-MM-dd'));
        setStartTime(format(startsAt, 'HH:mm'));

        if (event.ends_at) {
          const endsAt = new Date(event.ends_at);
          setEndDate(format(endsAt, 'yyyy-MM-dd'));
          setEndTime(format(endsAt, 'HH:mm'));
        } else {
          setEndDate('');
          setEndTime('');
        }

        setTitle(event.title);
        setDescription(event.description || '');
        setCategoryId(event.category_id || null);
        setTimezone(event.timezone);
        setLocationText(event.location_text || '');
        setRrule(event.rrule || '');
      } else if (initialDate) {
        setStartDate(format(initialDate, 'yyyy-MM-dd'));
        setStartTime(format(initialDate, 'HH:mm'));
        setEndDate('');
        setEndTime('');
        setTitle('');
        setDescription('');
        setCategoryId(null);
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
        setLocationText('');
        setRrule('');
      } else {
        setTitle('');
        setDescription('');
        setCategoryId(null);
        setStartDate('');
        setStartTime('');
        setEndDate('');
        setEndTime('');
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
        setLocationText('');
        setRrule('');
      }
    }
  }, [isOpen, event, initialDate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      alert('Please enter an event title');
      return;
    }

    if (!startDate || !startTime) {
      alert('Please enter start date and time');
      return;
    }

    setIsSubmitting(true);
    try {
      // Combine date and time
      const startsAt = `${startDate}T${startTime}`;

      // If end date is not provided, use start date
      let endsAt = '';
      if (endTime) {
        const effectiveEndDate = endDate || startDate;
        endsAt = `${effectiveEndDate}T${endTime}`;
      }

      const data: CreateEventRequest = {
        title: title.trim(),
        description: description.trim() || undefined,
        category_id: categoryId || undefined,
        starts_at: startsAt,
        ends_at: endsAt || undefined,
        timezone,
        location_text: locationText.trim() || undefined,
        rrule: rrule || undefined,
      };

      await onSubmit(data);
      onClose();
    } catch (error) {
      console.error('Failed to submit event:', error);
      alert('Failed to create event. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={event ? 'Edit Event' : 'Create Event'}
      >
        <form onSubmit={handleSubmit} className={styles.eventForm}>
          <div className={styles.formGroup}>
            <label className={styles.label}>
              Event Title<span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              className={styles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter event title"
              required
              autoFocus
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Description</label>
            <textarea
              className={styles.textarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter event description (optional)"
              rows={3}
            />
          </div>

          <CategoryPicker
            type="events"
            value={categoryId}
            onChange={setCategoryId}
            onManageCategories={() => setShowCategoryManager(true)}
          />

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label className={styles.label}>
                Start Date<span className={styles.required}>*</span>
              </label>
              <input
                type="date"
                className={styles.input}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>
                Start Time<span className={styles.required}>*</span>
              </label>
              <input
                type="time"
                className={styles.input}
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label className={styles.label}>End Date</label>
              <input
                type="date"
                className={styles.input}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="Optional, defaults to start date"
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>End Time</label>
              <input
                type="time"
                className={styles.input}
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Location</label>
            <input
              type="text"
              className={styles.input}
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
              placeholder="Event location (optional)"
            />
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Timezone</label>
            <select
              className={styles.select}
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              <option value={Intl.DateTimeFormat().resolvedOptions().timeZone}>
                {Intl.DateTimeFormat().resolvedOptions().timeZone} (Local)
              </option>
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York</option>
              <option value="America/Chicago">America/Chicago</option>
              <option value="America/Denver">America/Denver</option>
              <option value="America/Los_Angeles">America/Los_Angeles</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Paris">Europe/Paris</option>
              <option value="Asia/Tokyo">Asia/Tokyo</option>
            </select>
          </div>

          <RecurrenceInput type="event" value={rrule} onChange={setRrule} />

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
              {isSubmitting ? 'Saving...' : event ? 'Update Event' : 'Create Event'}
            </button>
          </div>
        </form>
      </Modal>

      <CategoryManager
        isOpen={showCategoryManager}
        onClose={() => setShowCategoryManager(false)}
        type="events"
      />
    </>
  );
}

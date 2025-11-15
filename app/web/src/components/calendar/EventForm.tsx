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

  // Separate date and time fields
  const [startDate, setStartDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endDate, setEndDate] = useState('');
  const [endTime, setEndTime] = useState('');

  const [isRecurring, setIsRecurring] = useState(false);
  const [recurringPattern, setRecurringPattern] = useState('DAILY');
  const [recurringInterval, setRecurringInterval] = useState('1');
  const [monthlyDayOfMonth, setMonthlyDayOfMonth] = useState('1');
  const [monthlyLastDay, setMonthlyLastDay] = useState(false);
  const [weeklyDays, setWeeklyDays] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
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
      setStartDate(format(initialDate, 'yyyy-MM-dd'));
      setStartTime(format(initialDate, 'HH:mm'));
      setEndDate('');
      setEndTime('');
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

    const options: any = {
      freq: RRule[freq],
      interval,
    };

    // Add monthly-specific options
    if (freq === 'MONTHLY') {
      if (monthlyLastDay) {
        options.bymonthday = -1; // Last day of month
      } else {
        const day = parseInt(monthlyDayOfMonth) || 1;
        options.bymonthday = day;
      }
    }

    // Add weekly-specific options
    if (freq === 'WEEKLY' && weeklyDays.length > 0) {
      options.byweekday = weeklyDays;
    }

    const rule = new RRule(options);
    return rule.toString();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      // Combine date and time
      const startsAt = `${startDate}T${startTime}`;

      // If end date is not provided, use start date
      let endsAt = '';
      if (endTime) {
        const effectiveEndDate = endDate || startDate;
        endsAt = `${effectiveEndDate}T${endTime}`;
      }

      const submitData = {
        ...formData,
        starts_at: startsAt,
        ends_at: endsAt || undefined,
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
    setStartDate('');
    setStartTime('');
    setEndDate('');
    setEndTime('');
    setIsRecurring(false);
    setRecurringPattern('DAILY');
    setRecurringInterval('1');
    setMonthlyDayOfMonth('1');
    setMonthlyLastDay(false);
    setWeeklyDays([]);
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

          <div className={styles.formGroup}>
            <label htmlFor="startDate">
              Start Date <span className={styles.required}>*</span>
            </label>
            <input
              type="date"
              id="startDate"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
              className={styles.input}
            />
          </div>

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label htmlFor="startTime">
                Start Time <span className={styles.required}>*</span>
              </label>
              <input
                type="time"
                id="startTime"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
                className={styles.input}
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="endTime">End Time (optional)</label>
              <input
                type="time"
                id="endTime"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className={styles.input}
              />
            </div>
          </div>

          {endTime && (
            <div className={styles.formGroup}>
              <label htmlFor="endDate">End Date (optional, defaults to start date)</label>
              <input
                type="date"
                id="endDate"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className={styles.input}
              />
            </div>
          )}

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
              <span>Recurring Task</span>
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
                    onChange={(e) => {
                      setRecurringPattern(e.target.value);
                      // Reset specific options when changing pattern
                      setWeeklyDays([]);
                      setMonthlyLastDay(false);
                      setMonthlyDayOfMonth('1');
                    }}
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

              {/* Weekly-specific options */}
              {recurringPattern === 'WEEKLY' && (
                <div className={styles.formGroup}>
                  <label>Days of Week</label>
                  <div className={styles.weekdayPicker}>
                    {[
                      { label: 'Sun', value: RRule.SU.weekday },
                      { label: 'Mon', value: RRule.MO.weekday },
                      { label: 'Tue', value: RRule.TU.weekday },
                      { label: 'Wed', value: RRule.WE.weekday },
                      { label: 'Thu', value: RRule.TH.weekday },
                      { label: 'Fri', value: RRule.FR.weekday },
                      { label: 'Sat', value: RRule.SA.weekday },
                    ].map((day) => (
                      <button
                        key={day.value}
                        type="button"
                        className={`${styles.weekdayBtn} ${
                          weeklyDays.includes(day.value) ? styles.weekdayBtnActive : ''
                        }`}
                        onClick={() => {
                          setWeeklyDays((prev) =>
                            prev.includes(day.value)
                              ? prev.filter((d) => d !== day.value)
                              : [...prev, day.value]
                          );
                        }}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                  <div className={styles.weekdayPresets}>
                    <button
                      type="button"
                      className={styles.btnPreset}
                      onClick={() => setWeeklyDays([RRule.MO.weekday, RRule.TU.weekday, RRule.WE.weekday, RRule.TH.weekday, RRule.FR.weekday])}
                    >
                      Workdays
                    </button>
                    <button
                      type="button"
                      className={styles.btnPreset}
                      onClick={() => setWeeklyDays([RRule.SA.weekday, RRule.SU.weekday])}
                    >
                      Weekends
                    </button>
                  </div>
                </div>
              )}

              {/* Monthly-specific options */}
              {recurringPattern === 'MONTHLY' && (
                <div className={styles.formGroup}>
                  <label>Day of Month</label>
                  <div className={styles.monthlyOptions}>
                    <label className={styles.checkboxLabel}>
                      <input
                        type="checkbox"
                        checked={monthlyLastDay}
                        onChange={(e) => setMonthlyLastDay(e.target.checked)}
                      />
                      <span>Last day of month</span>
                    </label>
                    {!monthlyLastDay && (
                      <div className={styles.formGroup} style={{ marginTop: 'var(--space-2)' }}>
                        <label htmlFor="monthlyDayOfMonth">Day (1-31)</label>
                        <input
                          type="number"
                          id="monthlyDayOfMonth"
                          value={monthlyDayOfMonth}
                          onChange={(e) => setMonthlyDayOfMonth(e.target.value)}
                          min="1"
                          max="31"
                          className={styles.input}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}
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

import { useState, useEffect } from 'react';
import styles from './RecurrenceInput.module.css';

interface RecurrenceInputProps {
  value: string; // RRULE string
  onChange: (rrule: string) => void;
  type: 'task' | 'event' | 'reminder';
}

type RecurrenceType = 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';

const DAYS_OF_WEEK = [
  { label: 'Sun', value: 'SU' },
  { label: 'Mon', value: 'MO' },
  { label: 'Tue', value: 'TU' },
  { label: 'Wed', value: 'WE' },
  { label: 'Thu', value: 'TH' },
  { label: 'Fri', value: 'FR' },
  { label: 'Sat', value: 'SA' },
];

export function RecurrenceInput({ value, onChange, type }: RecurrenceInputProps) {
  const [recurrenceType, setRecurrenceType] = useState<RecurrenceType>('none');
  const [selectedDays, setSelectedDays] = useState<string[]>([]);
  const [monthlyDay, setMonthlyDay] = useState<number>(1);
  const [isLastDayOfMonth, setIsLastDayOfMonth] = useState(false);
  const [yearlyDate, setYearlyDate] = useState<string>('');

  // Parse RRULE on mount or when value changes
  useEffect(() => {
    if (!value) {
      setRecurrenceType('none');
      return;
    }

    try {
      if (value.includes('FREQ=DAILY')) {
        setRecurrenceType('daily');
      } else if (value.includes('FREQ=WEEKLY')) {
        setRecurrenceType('weekly');
        // Parse BYDAY for weekly
        const byDayMatch = value.match(/BYDAY=([A-Z,]+)/);
        if (byDayMatch) {
          setSelectedDays(byDayMatch[1].split(','));
        }
      } else if (value.includes('FREQ=MONTHLY')) {
        setRecurrenceType('monthly');
        // Check if it's last day of month
        if (value.includes('BYMONTHDAY=-1')) {
          setIsLastDayOfMonth(true);
        } else {
          const byMonthDayMatch = value.match(/BYMONTHDAY=(\d+)/);
          if (byMonthDayMatch) {
            setMonthlyDay(parseInt(byMonthDayMatch[1]));
          }
        }
      } else if (value.includes('FREQ=YEARLY')) {
        setRecurrenceType('yearly');
        // Parse yearly date if available
        const byMonthMatch = value.match(/BYMONTH=(\d+)/);
        const byMonthDayMatch = value.match(/BYMONTHDAY=(\d+)/);
        if (byMonthMatch && byMonthDayMatch) {
          const month = String(byMonthMatch[1]).padStart(2, '0');
          const day = String(byMonthDayMatch[1]).padStart(2, '0');
          setYearlyDate(`${month}-${day}`);
        }
      }
    } catch (err) {
      console.error('Failed to parse RRULE:', err);
    }
  }, [value]);

  const generateRRule = (type: RecurrenceType): string => {
    switch (type) {
      case 'none':
        return '';
      case 'daily':
        return 'FREQ=DAILY';
      case 'weekly':
        if (selectedDays.length === 0) return '';
        return `FREQ=WEEKLY;BYDAY=${selectedDays.join(',')}`;
      case 'monthly':
        if (isLastDayOfMonth) {
          return 'FREQ=MONTHLY;BYMONTHDAY=-1';
        }
        return `FREQ=MONTHLY;BYMONTHDAY=${monthlyDay}`;
      case 'yearly':
        if (!yearlyDate) return '';
        const [month, day] = yearlyDate.split('-');
        return `FREQ=YEARLY;BYMONTH=${parseInt(month)};BYMONTHDAY=${parseInt(day)}`;
      default:
        return '';
    }
  };

  const handleRecurrenceTypeChange = (newType: RecurrenceType) => {
    setRecurrenceType(newType);
    const rrule = generateRRule(newType);
    onChange(rrule);
  };

  const handleDayToggle = (day: string) => {
    const newDays = selectedDays.includes(day)
      ? selectedDays.filter((d) => d !== day)
      : [...selectedDays, day];
    setSelectedDays(newDays);

    if (recurrenceType === 'weekly') {
      const rrule = newDays.length > 0 ? `FREQ=WEEKLY;BYDAY=${newDays.join(',')}` : '';
      onChange(rrule);
    }
  };

  const handleWeekdaysPreset = () => {
    const weekdays = ['MO', 'TU', 'WE', 'TH', 'FR'];
    setSelectedDays(weekdays);
    onChange(`FREQ=WEEKLY;BYDAY=${weekdays.join(',')}`);
  };

  const handleWeekendsPreset = () => {
    const weekends = ['SA', 'SU'];
    setSelectedDays(weekends);
    onChange(`FREQ=WEEKLY;BYDAY=${weekends.join(',')}`);
  };

  const handleMonthlyDayChange = (day: number) => {
    setMonthlyDay(day);
    setIsLastDayOfMonth(false);
    onChange(`FREQ=MONTHLY;BYMONTHDAY=${day}`);
  };

  const handleLastDayToggle = () => {
    const newIsLastDay = !isLastDayOfMonth;
    setIsLastDayOfMonth(newIsLastDay);
    if (newIsLastDay) {
      onChange('FREQ=MONTHLY;BYMONTHDAY=-1');
    } else {
      onChange(`FREQ=MONTHLY;BYMONTHDAY=${monthlyDay}`);
    }
  };

  const handleYearlyDateChange = (date: string) => {
    setYearlyDate(date);
    if (date) {
      const [month, day] = date.split('-');
      onChange(`FREQ=YEARLY;BYMONTH=${parseInt(month)};BYMONTHDAY=${parseInt(day)}`);
    }
  };

  return (
    <div className={styles.recurrenceInput}>
      <label className={styles.label}>Recurrence</label>

      <div className={styles.typeSelector}>
        {['none', 'daily', 'weekly', 'monthly', 'yearly'].map((type) => (
          <label key={type} className={styles.radioLabel}>
            <input
              type="radio"
              name="recurrence"
              value={type}
              checked={recurrenceType === type}
              onChange={() => handleRecurrenceTypeChange(type as RecurrenceType)}
            />
            <span>{type.charAt(0).toUpperCase() + type.slice(1)}</span>
          </label>
        ))}
      </div>

      {recurrenceType === 'weekly' && (
        <div className={styles.weeklyOptions}>
          <div className={styles.dayButtons}>
            {DAYS_OF_WEEK.map((day) => (
              <button
                key={day.value}
                type="button"
                className={`${styles.dayButton} ${
                  selectedDays.includes(day.value) ? styles.dayButtonActive : ''
                }`}
                onClick={() => handleDayToggle(day.value)}
              >
                {day.label}
              </button>
            ))}
          </div>
          <div className={styles.presets}>
            <button type="button" className={styles.presetButton} onClick={handleWeekdaysPreset}>
              Weekdays
            </button>
            <button type="button" className={styles.presetButton} onClick={handleWeekendsPreset}>
              Weekends
            </button>
          </div>
        </div>
      )}

      {recurrenceType === 'monthly' && (
        <div className={styles.monthlyOptions}>
          <label className={styles.monthlyLabel}>
            <span>Day of month:</span>
            <select
              className={styles.select}
              value={monthlyDay}
              onChange={(e) => handleMonthlyDayChange(parseInt(e.target.value))}
              disabled={isLastDayOfMonth}
            >
              {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={isLastDayOfMonth}
              onChange={handleLastDayToggle}
            />
            <span>Last day of month</span>
          </label>
        </div>
      )}

      {recurrenceType === 'yearly' && (
        <div className={styles.yearlyOptions}>
          <label className={styles.yearlyLabel}>
            <span>Date (MM-DD):</span>
            <input
              type="text"
              className={styles.input}
              placeholder="01-01"
              value={yearlyDate}
              onChange={(e) => handleYearlyDateChange(e.target.value)}
              pattern="\d{2}-\d{2}"
            />
          </label>
        </div>
      )}
    </div>
  );
}

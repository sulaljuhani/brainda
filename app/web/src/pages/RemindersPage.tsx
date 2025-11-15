import { useState, useMemo, useRef, useEffect } from 'react';
import { Plus, Bell, CheckCircle, Clock } from 'lucide-react';
import { useReminders } from '@hooks/useReminders';
import { useCalendar } from '@hooks/useCalendar';
import { ReminderList } from '@components/reminders/ReminderList';
import { ReminderForm } from '@components/reminders/ReminderForm';
import { EventForm } from '@components/calendar/EventForm';
import type { CreateReminderRequest, CreateEventRequest } from '../types/api';
import styles from './RemindersPage.module.css';

type TabType = 'active' | 'completed' | 'snoozed';

export default function RemindersPage() {
  const {
    reminders,
    loading,
    error,
    createReminder,
    snoozeReminder,
    completeReminder,
    deleteReminder,
  } = useReminders();

  // Fetch calendar events for the next 30 days
  const dateRange = useMemo(() => {
    const start = new Date();
    const end = new Date();
    end.setDate(end.getDate() + 30);
    return {
      start: start.toISOString(),
      end: end.toISOString(),
    };
  }, []);

  const { events, createEvent } = useCalendar(dateRange.start, dateRange.end);

  const [activeTab, setActiveTab] = useState<TabType>('active');
  const [showForm, setShowForm] = useState(false);
  const [showEventForm, setShowEventForm] = useState(false);
  const [showCreateDropdown, setShowCreateDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Filter reminders by status
  const filteredReminders = useMemo(() => {
    return reminders.filter((reminder) => reminder.status === activeTab);
  }, [reminders, activeTab]);

  // Count by status
  const counts = useMemo(() => {
    return {
      active: reminders.filter((r) => r.status === 'active').length,
      completed: reminders.filter((r) => r.status === 'completed').length,
      snoozed: reminders.filter((r) => r.status === 'snoozed').length,
    };
  }, [reminders]);

  const handleCreateReminder = async (data: CreateReminderRequest) => {
    await createReminder(data);
    setShowForm(false);
  };

  const handleSnooze = async (id: string, minutes: number) => {
    try {
      await snoozeReminder(id, minutes);
    } catch (err) {
      console.error('Failed to snooze reminder:', err);
    }
  };

  const handleComplete = async (id: string) => {
    try {
      await completeReminder(id);
    } catch (err) {
      console.error('Failed to complete reminder:', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteReminder(id);
    } catch (err) {
      console.error('Failed to delete reminder:', err);
    }
  };

  const tabs = [
    { id: 'active' as TabType, label: 'Active', icon: Bell, count: counts.active },
    { id: 'snoozed' as TabType, label: 'Snoozed', icon: Clock, count: counts.snoozed },
    { id: 'completed' as TabType, label: 'Completed', icon: CheckCircle, count: counts.completed },
  ];

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowCreateDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCreateEvent = () => {
    setShowEventForm(true);
    setShowCreateDropdown(false);
  };

  const handleCreateOneTimeTask = () => {
    setShowForm(true);
    setShowCreateDropdown(false);
  };

  const handleCreateRecurringTask = () => {
    setShowEventForm(true);
    setShowCreateDropdown(false);
  };

  const handleEventSubmit = async (data: CreateEventRequest) => {
    await createEvent(data);
    setShowEventForm(false);
  };

  return (
    <div className={styles.remindersPage}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.title}>Tasks</h1>
          <p className={styles.subtitle}>
            Manage your tasks and never miss important deadlines
          </p>
        </div>
        <div className={styles.createBtnContainer} ref={dropdownRef}>
          <button
            className={styles.createBtn}
            onClick={() => setShowCreateDropdown(!showCreateDropdown)}
          >
            <Plus size={20} />
            New Item
          </button>

          {showCreateDropdown && (
            <div className={styles.createDropdown}>
              <button
                className={styles.dropdownItem}
                onClick={handleCreateEvent}
              >
                Event
              </button>
              <button
                className={styles.dropdownItem}
                onClick={handleCreateRecurringTask}
              >
                Recurring Task
              </button>
              <button
                className={styles.dropdownItem}
                onClick={handleCreateOneTimeTask}
              >
                One-Time Task
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className={styles.errorBanner}>
          <p>{error}</p>
        </div>
      )}

      <div className={styles.tabs}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
            >
              <Icon size={18} />
              {tab.label}
              {tab.count > 0 && (
                <span className={styles.tabBadge}>{tab.count}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className={styles.content}>
        {loading ? (
          <div className={styles.loadingState}>
            <div className={styles.spinner}></div>
            <p>Loading reminders...</p>
          </div>
        ) : (
          <ReminderList
            reminders={filteredReminders}
            onSnooze={handleSnooze}
            onComplete={handleComplete}
            onDelete={handleDelete}
            emptyMessage={
              activeTab === 'active'
                ? 'No active tasks. Create one to get started!'
                : activeTab === 'snoozed'
                ? 'No snoozed tasks'
                : 'No completed tasks'
            }
          />
        )}
      </div>

      {showForm && (
        <ReminderForm
          onSubmit={handleCreateReminder}
          onCancel={() => setShowForm(false)}
        />
      )}

      {showEventForm && (
        <EventForm
          isOpen={showEventForm}
          onClose={() => setShowEventForm(false)}
          onSubmit={handleEventSubmit}
        />
      )}
    </div>
  );
}

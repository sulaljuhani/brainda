import { useState, useMemo } from 'react';
import { Plus, Bell, CheckCircle, Clock } from 'lucide-react';
import { useReminders } from '@hooks/useReminders';
import { ReminderList } from '@components/reminders/ReminderList';
import { ReminderForm } from '@components/reminders/ReminderForm';
import type { CreateReminderRequest } from '../types/api';
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

  const [activeTab, setActiveTab] = useState<TabType>('active');
  const [showForm, setShowForm] = useState(false);

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

  return (
    <div className={styles.remindersPage}>
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1 className={styles.title}>Tasks</h1>
          <p className={styles.subtitle}>
            Manage your tasks and never miss important deadlines
          </p>
        </div>
        <button onClick={() => setShowForm(true)} className={styles.createBtn}>
          <Plus size={20} />
          New Task
        </button>
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
    </div>
  );
}

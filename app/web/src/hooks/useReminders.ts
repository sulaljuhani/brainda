import { useState, useEffect } from 'react';
import { remindersService } from '@services/remindersService';
import type { Reminder, CreateReminderRequest } from '@types/*';

export function useReminders() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReminders = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await remindersService.getAll();
      setReminders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch reminders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReminders();
  }, []);

  const createReminder = async (data: CreateReminderRequest) => {
    const newReminder = await remindersService.create(data);
    setReminders((prev) => [newReminder, ...prev]);
    return newReminder;
  };

  const snoozeReminder = async (id: string, minutes: number) => {
    const updated = await remindersService.snooze(id, minutes);
    setReminders((prev) => prev.map((r) => (r.id === id ? updated : r)));
    return updated;
  };

  const completeReminder = async (id: string) => {
    const updated = await remindersService.complete(id);
    setReminders((prev) => prev.map((r) => (r.id === id ? updated : r)));
    return updated;
  };

  const deleteReminder = async (id: string) => {
    await remindersService.delete(id);
    setReminders((prev) => prev.filter((r) => r.id !== id));
  };

  return {
    reminders,
    loading,
    error,
    createReminder,
    snoozeReminder,
    completeReminder,
    deleteReminder,
    refetch: fetchReminders,
  };
}

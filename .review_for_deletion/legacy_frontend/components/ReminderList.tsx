'use client';

import { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface Reminder {
  id: string;
  title: string;
  body?: string;
  due_at_utc: string;
  status: string;
  repeat_rrule?: string;
}

export default function ReminderList() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReminders();
  }, []);

  const getToken = () => localStorage.getItem('session_token') ?? localStorage.getItem('api_token');

  async function fetchReminders() {
    const token = getToken();
    const response = await fetch('/api/v1/reminders', {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await response.json();
    setReminders(data);
    setLoading(false);
  }

  async function snoozeReminder(id: string, minutes: number) {
    const token = getToken();
    await fetch(`/api/v1/reminders/${id}/snooze`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ duration_minutes: minutes })
    });
    fetchReminders();
  }

  async function cancelReminder(id: string) {
    const token = getToken();
    await fetch(`/api/v1/reminders/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    });
    fetchReminders();
  }

  if (loading) return <div>Loading reminders...</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Reminders</h2>
      
      {reminders.length === 0 ? (
        <p className="text-gray-500">No active reminders</p>
      ) : (
        <div className="space-y-2">
          {reminders.map(reminder => (
            <div key={reminder.id} className="border p-4 rounded-lg">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{reminder.title}</h3>
                  {reminder.body && (
                    <p className="text-sm text-gray-600">{reminder.body}</p>
                  )}
                  <p className="text-sm text-gray-500">
                    {formatDistanceToNow(new Date(reminder.due_at_utc), { addSuffix: true })}
                  </p>
                  {reminder.repeat_rrule && (
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      Recurring
                    </span>
                  )}
                </div>
                
                <div className="flex gap-2">
                  <button
                    onClick={() => snoozeReminder(reminder.id, 15)}
                    className="text-sm px-3 py-1 bg-yellow-100 hover:bg-yellow-200 rounded"
                  >
                    Snooze 15m
                  </button>
                  <button
                    onClick={() => cancelReminder(reminder.id)}
                    className="text-sm px-3 py-1 bg-red-100 hover:bg-red-200 rounded"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

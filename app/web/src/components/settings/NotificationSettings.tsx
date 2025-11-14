import { useState, useEffect } from 'react';
import { settingsService } from '@services/settingsService';
import type { UserSettings } from '@types/*';
import styles from './SettingsSection.module.css';

export function NotificationSettings() {
  const [settings, setSettings] = useState<UserSettings>({
    notifications_enabled: true,
    email_notifications: true,
    reminder_notifications: true,
    calendar_notifications: true,
    theme: 'dark',
    font_size: 'medium',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await settingsService.getUserSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (key: keyof UserSettings, value: boolean) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    await saveSettings({ [key]: value });
  };

  const saveSettings = async (updates: Partial<UserSettings>) => {
    setSaving(true);
    setMessage(null);

    try {
      const updated = await settingsService.updateUserSettings(updates);
      setSettings(updated);
      setMessage({ type: 'success', text: 'Settings saved successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className={styles.section}>Loading...</div>;
  }

  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Notification Preferences</h2>
        <p className={styles.description}>Manage how you receive notifications</p>
      </div>

      <div className={styles.form}>
        <div className={styles.toggleGroup}>
          <div className={styles.toggleLabel}>
            <span className={styles.toggleTitle}>Enable Notifications</span>
            <span className={styles.toggleDescription}>
              Master switch for all notifications
            </span>
          </div>
          <button
            className={`${styles.toggle} ${settings.notifications_enabled ? styles.toggleActive : ''}`}
            onClick={() => handleToggle('notifications_enabled', !settings.notifications_enabled)}
            disabled={saving}
            aria-label="Toggle notifications"
          />
        </div>

        <div className={styles.toggleGroup}>
          <div className={styles.toggleLabel}>
            <span className={styles.toggleTitle}>Email Notifications</span>
            <span className={styles.toggleDescription}>
              Receive notifications via email
            </span>
          </div>
          <button
            className={`${styles.toggle} ${settings.email_notifications ? styles.toggleActive : ''}`}
            onClick={() => handleToggle('email_notifications', !settings.email_notifications)}
            disabled={saving || !settings.notifications_enabled}
            aria-label="Toggle email notifications"
          />
        </div>

        <div className={styles.toggleGroup}>
          <div className={styles.toggleLabel}>
            <span className={styles.toggleTitle}>Reminder Notifications</span>
            <span className={styles.toggleDescription}>
              Get notified when reminders are due
            </span>
          </div>
          <button
            className={`${styles.toggle} ${settings.reminder_notifications ? styles.toggleActive : ''}`}
            onClick={() => handleToggle('reminder_notifications', !settings.reminder_notifications)}
            disabled={saving || !settings.notifications_enabled}
            aria-label="Toggle reminder notifications"
          />
        </div>

        <div className={styles.toggleGroup}>
          <div className={styles.toggleLabel}>
            <span className={styles.toggleTitle}>Calendar Notifications</span>
            <span className={styles.toggleDescription}>
              Get notified about upcoming calendar events
            </span>
          </div>
          <button
            className={`${styles.toggle} ${settings.calendar_notifications ? styles.toggleActive : ''}`}
            onClick={() => handleToggle('calendar_notifications', !settings.calendar_notifications)}
            disabled={saving || !settings.notifications_enabled}
            aria-label="Toggle calendar notifications"
          />
        </div>

        {message && (
          <div className={`${styles.message} ${styles[message.type]}`}>
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}

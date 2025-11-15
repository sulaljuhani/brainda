import { useState, useEffect } from 'react';
import { settingsService } from '@services/settingsService';
import type { UserSettings } from '@/types';
import styles from './SettingsSection.module.css';

export function AppearanceSettings() {
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

  const handleThemeChange = async (theme: 'light' | 'dark' | 'auto') => {
    setSettings({ ...settings, theme });
    await saveSettings({ theme });
  };

  const handleFontSizeChange = async (fontSize: 'small' | 'medium' | 'large') => {
    setSettings({ ...settings, font_size: fontSize });
    await saveSettings({ font_size: fontSize });
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
        <h2 className={styles.title}>Appearance</h2>
        <p className={styles.description}>Customize how Brainda looks and feels</p>
      </div>

      <div className={styles.form}>
        <div className={styles.formGroup}>
          <label className={styles.label}>Theme</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
            <button
              className={`${styles.card} ${settings.theme === 'light' ? styles.cardActive : ''}`}
              onClick={() => handleThemeChange('light')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>☀️</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Light</div>
              </div>
            </button>
            <button
              className={`${styles.card} ${settings.theme === 'dark' ? styles.cardActive : ''}`}
              onClick={() => handleThemeChange('dark')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🌙</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Dark</div>
              </div>
            </button>
            <button
              className={`${styles.card} ${settings.theme === 'auto' ? styles.cardActive : ''}`}
              onClick={() => handleThemeChange('auto')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-2xl)', marginBottom: 'var(--space-2)' }}>🔄</div>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Auto</div>
              </div>
            </button>
          </div>
          <p className={styles.hint}>Choose your preferred color scheme</p>
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label}>Font Size</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
            <button
              className={`${styles.card} ${settings.font_size === 'small' ? styles.cardActive : ''}`}
              onClick={() => handleFontSizeChange('small')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Small</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                  Compact
                </div>
              </div>
            </button>
            <button
              className={`${styles.card} ${settings.font_size === 'medium' ? styles.cardActive : ''}`}
              onClick={() => handleFontSizeChange('medium')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Medium</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                  Default
                </div>
              </div>
            </button>
            <button
              className={`${styles.card} ${settings.font_size === 'large' ? styles.cardActive : ''}`}
              onClick={() => handleFontSizeChange('large')}
              disabled={saving}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            >
              <div style={{ textAlign: 'center', padding: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--font-medium)' }}>Large</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                  Comfortable
                </div>
              </div>
            </button>
          </div>
          <p className={styles.hint}>Adjust text size for better readability</p>
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label}>Timezone</label>
          <select
            className={styles.select}
            value={settings.timezone || 'UTC'}
            onChange={(e) => saveSettings({ timezone: e.target.value })}
            disabled={saving}
          >
            <option value="UTC">UTC (Coordinated Universal Time)</option>
            <option value="America/New_York">Eastern Time (ET)</option>
            <option value="America/Chicago">Central Time (CT)</option>
            <option value="America/Denver">Mountain Time (MT)</option>
            <option value="America/Los_Angeles">Pacific Time (PT)</option>
            <option value="Europe/London">London (GMT)</option>
            <option value="Europe/Paris">Paris (CET)</option>
            <option value="Asia/Tokyo">Tokyo (JST)</option>
            <option value="Asia/Shanghai">Shanghai (CST)</option>
            <option value="Australia/Sydney">Sydney (AEDT)</option>
          </select>
          <p className={styles.hint}>Used for displaying dates and times</p>
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

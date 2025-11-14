import { useState, useEffect } from 'react';
import { settingsService } from '@services/settingsService';
import type { GoogleCalendarSettings, OpenMemorySettings } from '@types/*';
import styles from './SettingsSection.module.css';

export function IntegrationSettings() {
  const [googleCalendar, setGoogleCalendar] = useState<GoogleCalendarSettings>({
    connected: false,
    sync_enabled: false,
  });
  const [openMemory, setOpenMemory] = useState<OpenMemorySettings>({
    enabled: false,
  });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const [gcal, omem] = await Promise.all([
        settingsService.getGoogleCalendarSettings().catch(() => ({ connected: false, sync_enabled: false })),
        settingsService.getOpenMemorySettings().catch(() => ({ enabled: false })),
      ]);
      setGoogleCalendar(gcal);
      setOpenMemory(omem);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogleCalendar = async () => {
    setMessage(null);
    try {
      const { auth_url } = await settingsService.connectGoogleCalendar();
      window.location.href = auth_url;
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to connect' });
    }
  };

  const handleDisconnectGoogleCalendar = async () => {
    setMessage(null);
    try {
      await settingsService.disconnectGoogleCalendar();
      setGoogleCalendar({ connected: false, sync_enabled: false });
      setMessage({ type: 'success', text: 'Google Calendar disconnected' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to disconnect' });
    }
  };

  const handleToggleGoogleCalendarSync = async () => {
    setMessage(null);
    try {
      await settingsService.updateGoogleCalendarSync(!googleCalendar.sync_enabled);
      setGoogleCalendar({ ...googleCalendar, sync_enabled: !googleCalendar.sync_enabled });
      setMessage({ type: 'success', text: 'Sync settings updated' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to update sync' });
    }
  };

  const handleToggleOpenMemory = async () => {
    setMessage(null);
    try {
      const updated = await settingsService.updateOpenMemorySettings({ enabled: !openMemory.enabled });
      setOpenMemory(updated);
      setMessage({ type: 'success', text: 'OpenMemory settings updated' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to update OpenMemory' });
    }
  };

  if (loading) {
    return <div className={styles.section}>Loading...</div>;
  }

  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Integrations</h2>
        <p className={styles.description}>Connect external services to enhance Brainda</p>
      </div>

      <div className={styles.form}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div>
              <h3 className={styles.cardTitle}>Google Calendar</h3>
              {googleCalendar.connected && (
                <span className={`${styles.badge} ${styles.badgeSuccess}`} style={{ marginLeft: 'var(--space-2)' }}>
                  Connected
                </span>
              )}
            </div>
          </div>
          <div className={styles.cardContent}>
            <p style={{ marginBottom: 'var(--space-4)' }}>
              Sync your calendar events between Brainda and Google Calendar for seamless scheduling.
            </p>

            {googleCalendar.connected ? (
              <>
                {googleCalendar.last_synced_at && (
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-4)' }}>
                    Last synced: {new Date(googleCalendar.last_synced_at).toLocaleString()}
                  </p>
                )}

                <div className={styles.toggleGroup} style={{ marginBottom: 'var(--space-4)' }}>
                  <div className={styles.toggleLabel}>
                    <span className={styles.toggleTitle}>Enable Sync</span>
                    <span className={styles.toggleDescription}>
                      Automatically sync events between Brainda and Google Calendar
                    </span>
                  </div>
                  <button
                    className={`${styles.toggle} ${googleCalendar.sync_enabled ? styles.toggleActive : ''}`}
                    onClick={handleToggleGoogleCalendarSync}
                    aria-label="Toggle Google Calendar sync"
                  />
                </div>

                <div className={styles.actions}>
                  <button className={styles.dangerButton} onClick={handleDisconnectGoogleCalendar}>
                    Disconnect
                  </button>
                </div>
              </>
            ) : (
              <div className={styles.actions}>
                <button className={styles.primaryButton} onClick={handleConnectGoogleCalendar}>
                  Connect Google Calendar
                </button>
              </div>
            )}
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div>
              <h3 className={styles.cardTitle}>OpenMemory</h3>
              {openMemory.enabled && (
                <span className={`${styles.badge} ${styles.badgeSuccess}`} style={{ marginLeft: 'var(--space-2)' }}>
                  Enabled
                </span>
              )}
            </div>
          </div>
          <div className={styles.cardContent}>
            <p style={{ marginBottom: 'var(--space-4)' }}>
              OpenMemory provides long-term conversational memory, allowing the AI to remember context across chat sessions.
            </p>

            <div className={styles.toggleGroup} style={{ marginBottom: 'var(--space-4)' }}>
              <div className={styles.toggleLabel}>
                <span className={styles.toggleTitle}>Enable OpenMemory</span>
                <span className={styles.toggleDescription}>
                  Store and retrieve conversation history for better context
                </span>
              </div>
              <button
                className={`${styles.toggle} ${openMemory.enabled ? styles.toggleActive : ''}`}
                onClick={handleToggleOpenMemory}
                aria-label="Toggle OpenMemory"
              />
            </div>

            {openMemory.url && (
              <div className={styles.formGroup}>
                <label className={styles.label}>OpenMemory Server URL</label>
                <div className={styles.readOnly}>{openMemory.url}</div>
              </div>
            )}
          </div>
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

import { useState, useEffect } from 'react';
import { api } from '@services/api';
import styles from './calendar.module.css';

interface GoogleCalendarStatus {
  connected: boolean;
  email?: string;
  sync_mode?: 'one_way' | 'two_way';
}

export function GoogleCalendarConnect() {
  const [status, setStatus] = useState<GoogleCalendarStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      setLoading(true);
      const response = await api.get<GoogleCalendarStatus>(
        '/calendar/google/status'
      );
      setStatus(response);
    } catch (error) {
      console.error('Failed to check Google Calendar status:', error);
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    try {
      // Get the authorization URL from the API
      const response = await api.get<{ authorization_url: string; state: string }>(
        '/calendar/google/connect'
      );
      // Redirect to Google OAuth flow
      window.location.href = response.authorization_url;
    } catch (error) {
      console.error('Failed to initiate Google Calendar connection:', error);
      alert('Failed to connect to Google Calendar. Please try again.');
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Google Calendar? This will stop syncing events.')) {
      return;
    }

    try {
      await api.delete('/calendar/google/disconnect');
      setStatus({ connected: false });
    } catch (error) {
      console.error('Failed to disconnect:', error);
      alert('Failed to disconnect Google Calendar');
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await api.post('/calendar/google/sync', {});
      alert('Sync started! Events will be synchronized in the background.');
    } catch (error) {
      console.error('Failed to start sync:', error);
      alert('Failed to start sync');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.googleCalendarCard}>
        <div className={styles.loadingSpinner}>Loading...</div>
      </div>
    );
  }

  return (
    <div className={styles.googleCalendarCard}>
      <div className={styles.googleCalendarHeader}>
        <h3>Google Calendar</h3>
        {status?.connected && (
          <span className={styles.connectedBadge}>Connected</span>
        )}
      </div>

      {status?.connected ? (
        <div className={styles.googleCalendarConnected}>
          <div className={styles.googleCalendarInfo}>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Account:</span>
              <span className={styles.infoValue}>{status.email || 'N/A'}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Sync Mode:</span>
              <span className={styles.infoValue}>
                {status.sync_mode === 'two_way'
                  ? 'Two-way (bidirectional)'
                  : 'One-way (Brainda → Google)'}
              </span>
            </div>
          </div>

          <div className={styles.googleCalendarActions}>
            <button
              onClick={handleSync}
              disabled={syncing}
              className={styles.btnPrimary}
            >
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>
            <button onClick={handleDisconnect} className={styles.btnDanger}>
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.googleCalendarDisconnected}>
          <p>Connect your Google Calendar to sync events automatically.</p>
          <button onClick={handleConnect} className={styles.btnPrimary}>
            Connect Google Calendar
          </button>
        </div>
      )}
    </div>
  );
}

'use client';

import { useCallback, useEffect, useState } from 'react';

type SyncStatus = {
  connected: boolean;
  sync_direction: 'one_way' | 'two_way' | null;
  last_sync: string | null;
  google_calendar_id?: string | null;
};

type ApiResponse<T> = {
  success?: boolean;
  message?: string;
} & T;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000/api/v1';

async function getJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export default function GoogleCalendarConnect({ token }: { token: string }) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const authorisedFetch = useCallback(
    async <T,>(path: string, init?: RequestInit) =>
      getJson<T>(path, {
        ...init,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(init?.headers ?? {}),
        },
      }),
    [token],
  );

  const refreshStatus = useCallback(async () => {
    try {
      const data = await authorisedFetch<SyncStatus>('/calendar/google/status');
      setStatus(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [authorisedFetch]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const startConnect = async () => {
    try {
      setLoading(true);
      const data = await authorisedFetch<{ authorization_url: string; state: string }>(
        '/calendar/google/connect',
        {
          method: 'GET',
        },
      );
      window.location.href = data.authorization_url;
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async () => {
    try {
      setLoading(true);
      await authorisedFetch<ApiResponse<Record<string, never>>>('/calendar/google/disconnect', {
        method: 'POST',
      });
      await refreshStatus();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const triggerSync = async () => {
    try {
      setLoading(true);
      await authorisedFetch<ApiResponse<Record<string, never>>>('/calendar/google/sync', {
        method: 'POST',
      });
      await refreshStatus();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!status) {
    return <div>Loading Google Calendar status…</div>;
  }

  return (
    <section className="google-calendar-settings" aria-live="polite">
      <header>
        <h3>Google Calendar Sync</h3>
        {error ? <p className="error">{error}</p> : null}
      </header>
      {status.connected ? (
        <div className="connected">
          <p>✅ Connected to Google Calendar</p>
          <p>
            Sync direction:{' '}
            <strong>{status.sync_direction === 'two_way' ? 'Two-way' : 'One-way'}</strong>
          </p>
          <p>
            Last sync:{' '}
            {status.last_sync ? new Date(status.last_sync).toLocaleString() : 'Never'}
          </p>
          <div className="actions">
            <button type="button" onClick={triggerSync} disabled={loading}>
              Sync Now
            </button>
            <button type="button" onClick={disconnect} disabled={loading} className="danger">
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <div className="disconnected">
          <p>Connect Google Calendar to mirror events into your personal assistant.</p>
          <button type="button" onClick={startConnect} disabled={loading}>
            Connect Google Calendar
          </button>
        </div>
      )}
    </section>
  );
}

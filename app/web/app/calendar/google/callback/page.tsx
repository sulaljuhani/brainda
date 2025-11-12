'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function GoogleCalendarCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const error = searchParams.get('error');
    if (error) {
      router.push('/settings?error=google_auth_failed');
      return;
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    if (code && state) {
      router.push('/settings?success=google_connected');
    }
  }, [router, searchParams]);

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h2>Connecting to Google Calendar…</h2>
      <p>You can close this window once the app redirects you.</p>
    </div>
  );
}

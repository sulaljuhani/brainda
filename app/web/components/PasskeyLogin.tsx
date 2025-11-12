'use client';

import { useState } from 'react';

function base64URLToUint8Array(value: string): Uint8Array {
  const padding = '='.repeat((4 - (value.length % 4)) % 4);
  const normalized = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
  const decoded = window.atob(normalized);
  const buffer = new Uint8Array(decoded.length);
  for (let i = 0; i < decoded.length; i += 1) {
    buffer[i] = decoded.charCodeAt(i);
  }
  return buffer;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

async function storeToken(key: string, value: string) {
  return new Promise<void>((resolve) => {
    const request = indexedDB.open('vib-auth', 1);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains('tokens')) {
        db.createObjectStore('tokens', { keyPath: 'key' });
      }
    };

    request.onsuccess = () => {
      const db = request.result;
      const transaction = db.transaction(['tokens'], 'readwrite');
      const store = transaction.objectStore('tokens');
      store.put({ key, value });
      transaction.oncomplete = () => {
        db.close();
        resolve();
      };
      transaction.onerror = () => {
        db.close();
        resolve();
      };
    };

    request.onerror = () => resolve();
  });
}

interface LoginResponse {
  challenge_id: string;
  options: string;
}

interface LoginCompleteResponse {
  success: boolean;
  session_token: string;
  expires_at: string;
}

export default function PasskeyLogin() {
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    try {
      const beginResponse = await fetch('/api/v1/auth/login/begin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!beginResponse.ok) {
        throw new Error('Failed to initiate login');
      }

      const beginPayload = (await beginResponse.json()) as LoginResponse;
      const options = JSON.parse(beginPayload.options);

      options.challenge = base64URLToUint8Array(options.challenge);
      if (Array.isArray(options.allowCredentials)) {
        options.allowCredentials = options.allowCredentials.map((cred: any) => ({
          ...cred,
          id: base64URLToUint8Array(cred.id),
        }));
      }

      const assertion = (await navigator.credentials.get({
        publicKey: options,
      })) as PublicKeyCredential | null;

      if (!assertion) {
        throw new Error('Authentication cancelled');
      }

      const assertionResponse = assertion.response as AuthenticatorAssertionResponse;

      const completeResponse = await fetch('/api/v1/auth/login/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: beginPayload.challenge_id,
          credential: {
            id: assertion.id,
            rawId: arrayBufferToBase64(assertion.rawId),
            type: assertion.type,
            response: {
              clientDataJSON: arrayBufferToBase64(assertionResponse.clientDataJSON),
              authenticatorData: arrayBufferToBase64(assertionResponse.authenticatorData),
              signature: arrayBufferToBase64(assertionResponse.signature),
              userHandle: assertionResponse.userHandle
                ? arrayBufferToBase64(assertionResponse.userHandle)
                : undefined,
            },
          },
        }),
      });

      if (!completeResponse.ok) {
        const detail = await completeResponse.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Login failed');
      }

      const completePayload = (await completeResponse.json()) as LoginCompleteResponse;
      localStorage.setItem('session_token', completePayload.session_token);
      localStorage.removeItem('api_token');
      await storeToken('session_token', completePayload.session_token);

      alert('Signed in successfully!');
      window.location.href = '/';
    } catch (error: any) {
      console.error('Login error', error);
      alert(error?.message || 'Unable to authenticate with passkey');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Sign in with your Passkey</h2>
      <button
        type="button"
        onClick={handleLogin}
        disabled={loading}
        className="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:opacity-50"
      >
        {loading ? 'Authenticating…' : 'Sign in'}
      </button>
      <p className="text-sm text-gray-500">
        Use your device biometrics or hardware key to sign in instantly. No password required.
      </p>
    </div>
  );
}

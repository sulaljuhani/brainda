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

interface RegisterResponse {
  user_id: string;
  options: string;
}

export default function PasskeyRegister() {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);

    try {
      const beginResponse = await fetch('/api/v1/auth/register/begin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, display_name: displayName }),
      });

      if (!beginResponse.ok) {
        throw new Error('Failed to start registration');
      }

      const beginPayload = (await beginResponse.json()) as RegisterResponse;
      const options = JSON.parse(beginPayload.options);

      options.challenge = base64URLToUint8Array(options.challenge);
      if (options.user?.id) {
        options.user.id = base64URLToUint8Array(options.user.id);
      }
      if (Array.isArray(options.excludeCredentials)) {
        options.excludeCredentials = options.excludeCredentials.map((cred: any) => ({
          ...cred,
          id: base64URLToUint8Array(cred.id),
        }));
      }

      const credential = (await navigator.credentials.create({
        publicKey: options,
      })) as PublicKeyCredential | null;

      if (!credential) {
        throw new Error('User cancelled credential creation');
      }

      const attestationResponse = credential.response as AuthenticatorAttestationResponse;

      const completeResponse = await fetch('/api/v1/auth/register/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: beginPayload.user_id,
          credential: {
            id: credential.id,
            rawId: arrayBufferToBase64(credential.rawId),
            type: credential.type,
            response: {
              clientDataJSON: arrayBufferToBase64(attestationResponse.clientDataJSON),
              attestationObject: arrayBufferToBase64(attestationResponse.attestationObject),
            },
          },
          device_name: deviceName || 'My Device',
        }),
      });

      if (!completeResponse.ok) {
        const detail = await completeResponse.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Registration failed');
      }

      alert('Passkey registered! You can now sign in.');
      window.location.href = '/login';
    } catch (error: any) {
      console.error('Registration error', error);
      alert(error?.message || 'Unable to register passkey');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleRegister} className="space-y-4 max-w-md">
      <h2 className="text-2xl font-semibold">Register with a Passkey</h2>

      <label className="block">
        <span className="text-sm font-medium">Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 w-full rounded border px-3 py-2"
          required
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium">Display name</span>
        <input
          type="text"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          className="mt-1 w-full rounded border px-3 py-2"
          required
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium">Device name (optional)</span>
        <input
          type="text"
          value={deviceName}
          onChange={(event) => setDeviceName(event.target.value)}
          className="mt-1 w-full rounded border px-3 py-2"
          placeholder="MacBook Pro"
        />
      </label>

      <button
        type="submit"
        disabled={loading}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Creating passkey…' : 'Create Passkey'}
      </button>

      <p className="text-sm text-gray-500">
        Use Touch ID, Face ID, Windows Hello, or a hardware key to register securely.
      </p>
    </form>
  );
}

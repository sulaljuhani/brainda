import { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authService } from '@services/authService';
import styles from './RegisterPage.module.css';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'form' | 'authenticating'>('form');
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Check if WebAuthn is supported
      if (!authService.isWebAuthnSupported()) {
        throw new Error('WebAuthn is not supported in this browser');
      }

      // Check if platform authenticator is available
      const isAvailable = await authService.isPlatformAuthenticatorAvailable();
      if (!isAvailable) {
        throw new Error(
          'No biometric authenticator found on this device. Please use a device with fingerprint or face recognition.'
        );
      }

      setStep('authenticating');

      // Begin registration
      const { user_id, options } = await authService.beginPasskeyRegistration(
        email,
        displayName || email.split('@')[0]
      );

      const publicKeyOptions = JSON.parse(options);

      // Create credential with the authenticator
      const credential = await navigator.credentials.create({
        publicKey: publicKeyOptions,
      });

      if (!credential) {
        throw new Error('No credential created');
      }

      // Complete registration
      await authService.completePasskeyRegistration(
        user_id,
        credential,
        deviceName || undefined
      );

      // Redirect to login page with success message
      navigate('/login', {
        state: { message: 'Registration successful! Please sign in.' },
      });
    } catch (err: any) {
      console.error('Registration error:', err);
      setError(err.message || 'Failed to register');
      setStep('form');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.title}>Create Your Account</h1>
          <p className={styles.subtitle}>
            {step === 'form'
              ? 'Register with a passkey for secure, passwordless access'
              : 'Follow your device prompt to create your passkey'}
          </p>
        </div>

        {error && (
          <div className={styles.error}>
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="currentColor"
              className={styles.errorIcon}
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            {error}
          </div>
        )}

        <div className={styles.content}>
          {step === 'form' ? (
            <form onSubmit={handleSubmit} className={styles.form}>
              <div className={styles.formGroup}>
                <label htmlFor="email" className={styles.label}>
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={styles.input}
                  placeholder="you@example.com"
                  required
                  disabled={loading}
                />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="displayName" className={styles.label}>
                  Display Name
                  <span className={styles.optional}>(Optional)</span>
                </label>
                <input
                  id="displayName"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className={styles.input}
                  placeholder="John Doe"
                  disabled={loading}
                />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="deviceName" className={styles.label}>
                  Device Name
                  <span className={styles.optional}>(Optional)</span>
                </label>
                <input
                  id="deviceName"
                  type="text"
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                  className={styles.input}
                  placeholder="My Laptop"
                  disabled={loading}
                />
                <p className={styles.hint}>
                  Helps you identify this device when managing your passkeys
                </p>
              </div>

              <button type="submit" disabled={loading} className={styles.submitButton}>
                {loading ? (
                  <>
                    <span className={styles.spinner} />
                    Creating Account...
                  </>
                ) : (
                  <>
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M12 2a5 5 0 0 1 5 5c0 2.5-2.3 4-5 4s-5-1.5-5-4a5 5 0 0 1 5-5Z" />
                      <path d="M12 14a9 9 0 0 0-9 9h18a9 9 0 0 0-9-9Z" />
                      <path d="M20 21v-8a2 2 0 0 0-2-2h-2" />
                    </svg>
                    Create Account with Passkey
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className={styles.authenticating}>
              <div className={styles.authIcon}>
                <svg
                  width="64"
                  height="64"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className={styles.authIconSvg}
                >
                  <path d="M12 2a5 5 0 0 1 5 5c0 2.5-2.3 4-5 4s-5-1.5-5-4a5 5 0 0 1 5-5Z" />
                  <path d="M12 14a9 9 0 0 0-9 9h18a9 9 0 0 0-9-9Z" />
                  <path d="M20 21v-8a2 2 0 0 0-2-2h-2" />
                </svg>
              </div>
              <p className={styles.authText}>
                Please follow the prompt on your device to create your passkey.
              </p>
            </div>
          )}

          <div className={styles.divider}>
            <span className={styles.dividerText}>or</span>
          </div>

          <div className={styles.loginPrompt}>
            <p>Already have an account?</p>
            <Link to="/login" className={styles.loginLink}>
              Sign in
            </Link>
          </div>
        </div>

        <div className={styles.footer}>
          <p className={styles.footerText}>
            By registering, you'll create a passkey that uses your device's biometric
            authentication (fingerprint, face ID) or security key. Your credentials never
            leave your device.
          </p>
        </div>
      </div>
    </div>
  );
}

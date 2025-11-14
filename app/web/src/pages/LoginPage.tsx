import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@contexts/AuthContext';
import { authService } from '@services/authService';
import styles from './LoginPage.module.css';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  // Get the redirect location from state (set by ProtectedRoute)
  const from = (location.state as any)?.from?.pathname || '/';

  const handlePasskeyLogin = async () => {
    setLoading(true);
    setError(null);

    try {
      // Check if WebAuthn is supported
      if (!authService.isWebAuthnSupported()) {
        throw new Error('WebAuthn is not supported in this browser');
      }

      // Begin passkey login
      const { challenge_id, options } = await authService.beginPasskeyLogin();
      const publicKeyOptions = JSON.parse(options);

      // Request credentials from the authenticator
      const credential = await navigator.credentials.get({
        publicKey: publicKeyOptions,
      });

      if (!credential) {
        throw new Error('No credential returned');
      }

      // Complete login with the credential
      const response = await authService.completePasskeyLogin(
        challenge_id,
        credential
      );

      // Store session token and update auth context
      await login(response.session_token);

      // Redirect to the originally requested page
      navigate(from, { replace: true });
    } catch (err: any) {
      console.error('Passkey login error:', err);
      setError(err.message || 'Failed to login with passkey');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.title}>Welcome to Brainda</h1>
          <p className={styles.subtitle}>Sign in to access your knowledge base</p>
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
          <button
            onClick={handlePasskeyLogin}
            disabled={loading}
            className={styles.passkeyButton}
          >
            {loading ? (
              <>
                <span className={styles.spinner} />
                Authenticating...
              </>
            ) : (
              <>
                <svg
                  width="24"
                  height="24"
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
                Sign in with Passkey
              </>
            )}
          </button>

          <div className={styles.divider}>
            <span className={styles.dividerText}>or</span>
          </div>

          <div className={styles.registerPrompt}>
            <p>Don't have an account?</p>
            <Link to="/register" className={styles.registerLink}>
              Create one with a passkey
            </Link>
          </div>
        </div>

        <div className={styles.footer}>
          <p className={styles.footerText}>
            Passkeys use your device's biometric authentication (fingerprint, face ID) or
            security key for secure, passwordless login.
          </p>
        </div>
      </div>
    </div>
  );
}

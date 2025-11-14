import { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@contexts/AuthContext';
import { authService } from '@services/authService';
import styles from './RegisterPage.module.css';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validation
    if (username.length < 3) {
      setError('Username must be at least 3 characters');
      setLoading(false);
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    try {
      const response = await authService.register(
        username,
        password,
        email || undefined,
        displayName || undefined
      );

      // Store session token and update auth context
      await login(response.session_token);

      // Redirect to home page
      navigate('/', { replace: true });
    } catch (err: any) {
      console.error('Registration error:', err);
      setError(err.message || 'Failed to create account');
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
            Register to start using Brainda
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
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.formGroup}>
              <label htmlFor="username" className={styles.label}>
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={styles.input}
                placeholder="john_doe"
                required
                disabled={loading}
                autoComplete="username"
                autoFocus
                minLength={3}
              />
              <p className={styles.hint}>
                At least 3 characters, letters, numbers, hyphens and underscores only
              </p>
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="email" className={styles.label}>
                Email Address
                <span className={styles.optional}>(Optional)</span>
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={styles.input}
                placeholder="you@example.com"
                disabled={loading}
                autoComplete="email"
              />
              <p className={styles.hint}>
                Used for notifications (if you set them up)
              </p>
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
                autoComplete="name"
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="password" className={styles.label}>
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.input}
                placeholder="At least 8 characters"
                required
                disabled={loading}
                autoComplete="new-password"
                minLength={8}
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="confirmPassword" className={styles.label}>
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={styles.input}
                placeholder="Re-enter your password"
                required
                disabled={loading}
                autoComplete="new-password"
                minLength={8}
              />
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
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <line x1="19" y1="8" x2="19" y2="14" />
                    <line x1="22" y1="11" x2="16" y2="11" />
                  </svg>
                  Create Account
                </>
              )}
            </button>
          </form>

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
            By creating an account, you can access all features including notes, documents,
            semantic search, and AI-powered chat.
          </p>
        </div>
      </div>
    </div>
  );
}

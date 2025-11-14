import { useState } from 'react';
import { settingsService } from '@services/settingsService';
import styles from './SettingsSection.module.css';

export function SecuritySettings() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: 'New passwords do not match' });
      return;
    }

    if (newPassword.length < 8) {
      setMessage({ type: 'error', text: 'Password must be at least 8 characters' });
      return;
    }

    setLoading(true);

    try {
      await settingsService.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setMessage({ type: 'success', text: 'Password changed successfully' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to change password' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Security Settings</h2>
        <p className={styles.description}>Manage your password and authentication methods</p>
      </div>

      <div className={styles.form}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3 className={styles.cardTitle}>Change Password</h3>
          </div>
          <form onSubmit={handlePasswordChange}>
            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="current-password">
                Current Password
              </label>
              <input
                type="password"
                id="current-password"
                className={styles.input}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="new-password">
                New Password
              </label>
              <input
                type="password"
                id="new-password"
                className={styles.input}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <p className={styles.hint}>Must be at least 8 characters</p>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="confirm-password">
                Confirm New Password
              </label>
              <input
                type="password"
                id="confirm-password"
                className={styles.input}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>

            {message && (
              <div className={`${styles.message} ${styles[message.type]}`}>
                {message.text}
              </div>
            )}

            <div className={styles.actions}>
              <button type="submit" className={styles.primaryButton} disabled={loading}>
                {loading ? 'Changing...' : 'Change Password'}
              </button>
            </div>
          </form>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3 className={styles.cardTitle}>Passkeys (WebAuthn)</h3>
            <span className={`${styles.badge} ${styles.badgeSuccess}`}>Recommended</span>
          </div>
          <div className={styles.cardContent}>
            <p>Passkeys provide a more secure and convenient way to sign in using biometrics or security keys.</p>
            <div className={styles.actions} style={{ marginTop: 'var(--space-4)' }}>
              <button className={styles.secondaryButton}>
                Manage Passkeys
              </button>
            </div>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3 className={styles.cardTitle}>Two-Factor Authentication (TOTP)</h3>
          </div>
          <div className={styles.cardContent}>
            <p>Add an extra layer of security by requiring a time-based one-time password when signing in.</p>
            <div className={styles.actions} style={{ marginTop: 'var(--space-4)' }}>
              <button className={styles.secondaryButton}>
                Enable 2FA
              </button>
            </div>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3 className={styles.cardTitle}>Active Sessions</h3>
          </div>
          <div className={styles.cardContent}>
            <p>View and manage active sessions across all devices.</p>
            <div className={styles.actions} style={{ marginTop: 'var(--space-4)' }}>
              <button className={styles.dangerButton}>
                Revoke All Sessions
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

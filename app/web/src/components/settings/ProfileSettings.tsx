import { useState, useEffect } from 'react';
import { useAuth } from '@contexts/AuthContext';
import { settingsService } from '@services/settingsService';
import styles from './SettingsSection.module.css';

export function ProfileSettings() {
  const { user } = useAuth();
  const [username, setUsername] = useState(user?.username || '');
  const [email, setEmail] = useState(user?.email || '');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (user) {
      setUsername(user.username);
      setEmail(user.email || '');
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      await settingsService.updateProfile({
        username: username !== user?.username ? username : undefined,
        email: email !== user?.email ? email : undefined,
      });
      setMessage({ type: 'success', text: 'Profile updated successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Failed to update profile' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Profile Information</h2>
        <p className={styles.description}>Update your account profile information</p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.formGroup}>
          <label className={styles.label} htmlFor="username">
            Username
          </label>
          <input
            type="text"
            id="username"
            className={styles.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            maxLength={50}
          />
          <p className={styles.hint}>Your unique username across Brainda</p>
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label} htmlFor="email">
            Email Address
          </label>
          <input
            type="email"
            id="email"
            className={styles.input}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <p className={styles.hint}>Used for notifications and account recovery</p>
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label}>User ID</label>
          <div className={styles.readOnly}>{user?.id}</div>
          <p className={styles.hint}>Your unique identifier (read-only)</p>
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label}>Account Created</label>
          <div className={styles.readOnly}>
            {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
          </div>
        </div>

        {message && (
          <div className={`${styles.message} ${styles[message.type]}`}>
            {message.text}
          </div>
        )}

        <div className={styles.actions}>
          <button type="submit" className={styles.primaryButton} disabled={loading}>
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

import { useNavigate } from 'react-router-dom';
import { useAuth } from '@contexts/AuthContext';
import { Settings } from 'lucide-react';
import styles from './UserMenu.module.css';

export function UserMenu() {
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return null;
  }

  const getInitials = (username: string) => {
    return username
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const handleClick = () => {
    navigate('/settings');
  };

  return (
    <button
      className={styles.userButton}
      onClick={handleClick}
      aria-label="Go to settings"
    >
      <div className={styles.avatar}>
        {user.email ? getInitials(user.email) : getInitials(user.username)}
      </div>
      <span className={styles.username}>{user.username}</span>
      <Settings size={18} className={styles.settingsIcon} />
    </button>
  );
}

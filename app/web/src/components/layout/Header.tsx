import { useNavigate } from 'react-router-dom';
import { UserMenu } from '@components/auth/UserMenu';
import { HamburgerMenu } from './HamburgerMenu';
import { Bell, Settings } from 'lucide-react';
import styles from './Header.module.css';

interface HeaderProps {
  onMenuToggle?: () => void;
  menuOpen?: boolean;
}

export function Header({ onMenuToggle, menuOpen = false }: HeaderProps) {
  const navigate = useNavigate();

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        {onMenuToggle && (
          <HamburgerMenu isOpen={menuOpen} onClick={onMenuToggle} />
        )}

        <div className={styles.logo} onClick={() => navigate('/')}>
          Brainda
        </div>
      </div>

      <div className={styles.right}>
        <button className={styles.iconButton} aria-label="Notifications">
          <Bell size={20} />
          {/* Add badge if needed */}
        </button>

        <button
          className={styles.iconButton}
          aria-label="Settings"
          onClick={() => navigate('/settings')}
        >
          <Settings size={20} />
        </button>
      </div>
    </header>
  );
}

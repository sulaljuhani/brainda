import { useNavigate, useLocation } from 'react-router-dom';
import styles from './MobileNav.module.css';

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: '💬', path: '/' },
  { id: 'notes', label: 'Notes', icon: '📝', path: '/notes' },
  { id: 'calendar', label: 'Calendar', icon: '📆', path: '/calendar' },
  { id: 'search', label: 'Search', icon: '🔎', path: '/search' },
];

export function MobileNav() {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <nav className={styles.mobileNav} role="navigation" aria-label="Mobile navigation">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
          onClick={() => navigate(item.path)}
          aria-label={item.label}
          aria-current={isActive(item.path) ? 'page' : undefined}
        >
          <span className={styles.navIcon} role="img" aria-hidden="true">
            {item.icon}
          </span>
          <span className={styles.navLabel}>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

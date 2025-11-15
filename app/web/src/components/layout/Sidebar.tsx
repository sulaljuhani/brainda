import { useNavigate, useLocation } from 'react-router-dom';
import { useRef, useEffect } from 'react';
import { useSwipeGesture } from '@hooks/useSwipeGesture';
import { useIsMobileOrTablet } from '@hooks/useMediaQuery';
import styles from './Sidebar.module.css';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: '💬', path: '/' },
  { id: 'notes', label: 'Notes', icon: '📝', path: '/notes' },
  { id: 'documents', label: 'Documents', icon: '📄', path: '/documents' },
  { id: 'tasks', label: 'Tasks', icon: '✓', path: '/tasks' },
  { id: 'events', label: 'Events', icon: '📅', path: '/events' },
  { id: 'reminders', label: 'Reminders', icon: '⏰', path: '/reminders' },
  { id: 'calendar', label: 'Calendar', icon: '📆', path: '/calendar' },
  { id: 'search', label: 'Search', icon: '🔎', path: '/search' },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const sidebarRef = useRef<HTMLElement>(null);
  const isMobileOrTablet = useIsMobileOrTablet();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  // Add swipe left gesture to close sidebar on mobile
  useSwipeGesture(sidebarRef, {
    onSwipeLeft: () => {
      if (!collapsed && isMobileOrTablet) {
        onToggle();
      }
    },
  });

  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    if (!isMobileOrTablet || collapsed) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        onToggle();
      }
    };

    // Small delay to prevent immediate closing after opening
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [collapsed, onToggle, isMobileOrTablet]);

  return (
    <aside
      ref={sidebarRef}
      id="mobile-sidebar"
      className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}
    >
      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
            onClick={() => navigate(item.path)}
            aria-label={item.label}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className={styles.divider} />

      {!collapsed && (
        <div className={styles.recentSection}>
          <div className={styles.sectionTitle}>Recent</div>
          <div className={styles.recentItem}>Project notes</div>
          <div className={styles.recentItem}>Meeting summary</div>
          <div className={styles.recentItem}>Ideas brainstorm</div>
        </div>
      )}

      <div className={styles.collapseSection}>
        <button className={styles.collapseButton} onClick={onToggle}>
          <span>{collapsed ? '➡️' : '⬅️'}</span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

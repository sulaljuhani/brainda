import { ReactNode, useState, useEffect } from 'react';
import { Header } from '@components/layout/Header';
import { Sidebar } from '@components/layout/Sidebar';
import { MobileNav } from '@components/layout/MobileNav';
import { GlobalSearch } from '@components/search/GlobalSearch';
import { useLocalStorage } from '@hooks/useLocalStorage';
import { useIsMobileOrTablet } from '@hooks/useMediaQuery';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const isMobileOrTablet = useIsMobileOrTablet();
  // On mobile/tablet, sidebar starts collapsed (hidden)
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage(
    'sidebar-collapsed',
    isMobileOrTablet
  );
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Auto-collapse sidebar on mobile/tablet resize
  useEffect(() => {
    if (isMobileOrTablet) {
      setSidebarCollapsed(true);
    }
  }, [isMobileOrTablet, setSidebarCollapsed]);

  // Global keyboard shortcut for Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K on Mac, Ctrl+K on Windows/Linux
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
      // Escape to close sidebar on mobile
      if (e.key === 'Escape' && !sidebarCollapsed && isMobileOrTablet) {
        setSidebarCollapsed(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [sidebarCollapsed, isMobileOrTablet, setSidebarCollapsed]);

  return (
    <div className={styles.layout}>
      <Header
        onMenuToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        menuOpen={!sidebarCollapsed}
      />
      <div className={styles.mainContainer}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <main className={styles.content}>
          {children}
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <MobileNav />

      {/* Backdrop overlay for mobile sidebar */}
      {!sidebarCollapsed && isMobileOrTablet && (
        <div
          className={styles.backdrop}
          onClick={() => setSidebarCollapsed(true)}
          aria-hidden="true"
        />
      )}

      <GlobalSearch isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
    </div>
  );
}

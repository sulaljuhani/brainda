import { ReactNode, useState, useEffect } from 'react';
import { Header } from '@components/layout/Header';
import { Sidebar } from '@components/layout/Sidebar';
import { GlobalSearch } from '@components/search/GlobalSearch';
import { useLocalStorage } from '@hooks/useLocalStorage';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage('sidebar-collapsed', false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Global keyboard shortcut for Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K on Mac, Ctrl+K on Windows/Linux
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className={styles.layout}>
      <Header />
      <div className={styles.mainContainer}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <main className={styles.content}>
          {children}
        </main>
      </div>
      <GlobalSearch isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
    </div>
  );
}

import { ReactNode, useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
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
  const location = useLocation();
  const isMobileOrTablet = useIsMobileOrTablet();
  const isChatPage = location.pathname === '/' || location.pathname === '/chat';
  const [, forceUpdate] = useState({});
  // On mobile/tablet, sidebar starts collapsed (hidden)
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage(
    'sidebar-collapsed',
    isMobileOrTablet
  );
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Get chat handlers from ChatPage if on chat page
  const chatHandlers = isChatPage ? (window as any).__chatPageHandlers : null;

  // Force re-render when chat handlers are available
  useEffect(() => {
    if (isChatPage && !chatHandlers) {
      const timer = setTimeout(() => forceUpdate({}), 100);
      return () => clearTimeout(timer);
    }
  }, [isChatPage, chatHandlers]);

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
      <div className={styles.mainContainer}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          currentConversationId={chatHandlers?.currentConversationId}
          onConversationSelect={chatHandlers?.onConversationSelect}
          onNewConversation={chatHandlers?.onNewConversation}
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

import { ReactNode } from 'react';
import { Header } from '@components/layout/Header';
import { Sidebar } from '@components/layout/Sidebar';
import { useLocalStorage } from '@hooks/useLocalStorage';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useLocalStorage('sidebar-collapsed', false);

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
    </div>
  );
}

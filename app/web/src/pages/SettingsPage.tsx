import { useState } from 'react';
import { ProfileSettings } from '@components/settings/ProfileSettings';
import { SecuritySettings } from '@components/settings/SecuritySettings';
import { NotificationSettings } from '@components/settings/NotificationSettings';
import { AppearanceSettings } from '@components/settings/AppearanceSettings';
import { IntegrationSettings } from '@components/settings/IntegrationSettings';
import { AISettings } from '@components/settings/AISettings';
import DashboardPage from './DashboardPage';
import CategoriesPage from './CategoriesPage';
import {
  User,
  Lock,
  Bot,
  Bell,
  Palette,
  Link,
  BarChart3,
  Tag
} from 'lucide-react';
import styles from './SettingsPage.module.css';

type SettingSection = 'profile' | 'security' | 'notifications' | 'appearance' | 'integrations' | 'ai' | 'dashboard' | 'categories';

interface SectionConfig {
  id: SettingSection;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const sections: SectionConfig[] = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'security', label: 'Security', icon: Lock },
  { id: 'ai', label: 'AI & Chat', icon: Bot },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'integrations', label: 'Integrations', icon: Link },
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'categories', label: 'Categories', icon: Tag },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SettingSection>('profile');

  const renderSection = () => {
    switch (activeSection) {
      case 'profile':
        return <ProfileSettings />;
      case 'security':
        return <SecuritySettings />;
      case 'ai':
        return <AISettings />;
      case 'notifications':
        return <NotificationSettings />;
      case 'appearance':
        return <AppearanceSettings />;
      case 'integrations':
        return <IntegrationSettings />;
      case 'dashboard':
        return <DashboardPage />;
      case 'categories':
        return <CategoriesPage />;
      default:
        return <ProfileSettings />;
    }
  };

  return (
    <div className={styles.settingsPage}>
      <div className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
        <p className={styles.subtitle}>Manage your account settings and preferences</p>
      </div>

      <div className={styles.content}>
        <aside className={styles.sidebar}>
          <nav className={styles.nav}>
            {sections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  className={`${styles.navItem} ${
                    activeSection === section.id ? styles.navItemActive : ''
                  }`}
                  onClick={() => setActiveSection(section.id)}
                >
                  <span className={styles.navIcon}>
                    <Icon size={20} />
                  </span>
                  <span className={styles.navLabel}>{section.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <main className={styles.main}>{renderSection()}</main>
      </div>
    </div>
  );
}

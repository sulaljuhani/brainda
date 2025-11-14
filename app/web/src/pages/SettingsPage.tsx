import { useState } from 'react';
import { ProfileSettings } from '@components/settings/ProfileSettings';
import { SecuritySettings } from '@components/settings/SecuritySettings';
import { NotificationSettings } from '@components/settings/NotificationSettings';
import { AppearanceSettings } from '@components/settings/AppearanceSettings';
import { IntegrationSettings } from '@components/settings/IntegrationSettings';
import styles from './SettingsPage.module.css';

type SettingSection = 'profile' | 'security' | 'notifications' | 'appearance' | 'integrations';

interface SectionConfig {
  id: SettingSection;
  label: string;
  icon: string;
}

const sections: SectionConfig[] = [
  { id: 'profile', label: 'Profile', icon: '👤' },
  { id: 'security', label: 'Security', icon: '🔒' },
  { id: 'notifications', label: 'Notifications', icon: '🔔' },
  { id: 'appearance', label: 'Appearance', icon: '🎨' },
  { id: 'integrations', label: 'Integrations', icon: '🔗' },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SettingSection>('profile');

  const renderSection = () => {
    switch (activeSection) {
      case 'profile':
        return <ProfileSettings />;
      case 'security':
        return <SecuritySettings />;
      case 'notifications':
        return <NotificationSettings />;
      case 'appearance':
        return <AppearanceSettings />;
      case 'integrations':
        return <IntegrationSettings />;
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
            {sections.map((section) => (
              <button
                key={section.id}
                className={`${styles.navItem} ${
                  activeSection === section.id ? styles.navItemActive : ''
                }`}
                onClick={() => setActiveSection(section.id)}
              >
                <span className={styles.navIcon}>{section.icon}</span>
                <span className={styles.navLabel}>{section.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className={styles.main}>{renderSection()}</main>
      </div>
    </div>
  );
}

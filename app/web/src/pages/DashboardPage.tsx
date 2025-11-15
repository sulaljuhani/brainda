import { useState, useEffect } from 'react';
import { apiClient } from '@services/apiClient';
import styles from './DashboardPage.module.css';

interface Stats {
  tasks: {
    total: number;
    active: number;
    completed: number;
    with_subtasks: number;
  };
  events: {
    total: number;
    upcoming: number;
    past: number;
    recurring: number;
  };
  reminders: {
    total: number;
    active: number;
    completed: number;
    recurring: number;
  };
  chat: {
    total_conversations: number;
    total_messages: number;
    avg_messages_per_conversation: number;
  };
  notes_count: number;
  documents_count: number;
}

interface StatCardProps {
  title: string;
  icon: string;
  stats: Array<{ label: string; value: number | string; highlight?: boolean }>;
}

function StatCard({ title, icon, stats }: StatCardProps) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statHeader}>
        <span className={styles.statIcon}>{icon}</span>
        <h3 className={styles.statTitle}>{title}</h3>
      </div>
      <div className={styles.statGrid}>
        {stats.map((stat, index) => (
          <div
            key={index}
            className={`${styles.statItem} ${stat.highlight ? styles.statHighlight : ''}`}
          >
            <div className={styles.statValue}>{stat.value}</div>
            <div className={styles.statLabel}>{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.get<Stats>('/stats/overview');
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load statistics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.dashboardPage}>
        <div className={styles.loading}>
          <div className={styles.spinner}></div>
          <p>Loading statistics...</p>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className={styles.dashboardPage}>
        <div className={styles.error}>
          <p>Error: {error || 'Failed to load statistics'}</p>
          <button className={styles.retryBtn} onClick={fetchStats}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const completionRate = stats.tasks.total > 0
    ? Math.round((stats.tasks.completed / stats.tasks.total) * 100)
    : 0;

  return (
    <div className={styles.dashboardPage}>
      <div className={styles.header}>
        <h1 className={styles.title}>Dashboard</h1>
        <p className={styles.subtitle}>Overview of your productivity and activity</p>
      </div>

      <div className={styles.statsGrid}>
        <StatCard
          title="Tasks"
          icon="✓"
          stats={[
            { label: 'Total', value: stats.tasks.total, highlight: true },
            { label: 'Active', value: stats.tasks.active },
            { label: 'Completed', value: stats.tasks.completed },
            { label: 'Completion Rate', value: `${completionRate}%` },
          ]}
        />

        <StatCard
          title="Events"
          icon="📅"
          stats={[
            { label: 'Total', value: stats.events.total, highlight: true },
            { label: 'Upcoming', value: stats.events.upcoming },
            { label: 'Past', value: stats.events.past },
            { label: 'Recurring', value: stats.events.recurring },
          ]}
        />

        <StatCard
          title="Reminders"
          icon="⏰"
          stats={[
            { label: 'Total', value: stats.reminders.total, highlight: true },
            { label: 'Active', value: stats.reminders.active },
            { label: 'Completed', value: stats.reminders.completed },
            { label: 'Recurring', value: stats.reminders.recurring },
          ]}
        />

        <StatCard
          title="Chat"
          icon="💬"
          stats={[
            { label: 'Conversations', value: stats.chat.total_conversations, highlight: true },
            { label: 'Messages', value: stats.chat.total_messages },
            {
              label: 'Avg/Conversation',
              value: stats.chat.avg_messages_per_conversation.toFixed(1),
            },
          ]}
        />

        <StatCard
          title="Notes"
          icon="📝"
          stats={[
            { label: 'Total Notes', value: stats.notes_count, highlight: true },
          ]}
        />

        <StatCard
          title="Documents"
          icon="📄"
          stats={[
            { label: 'Total Documents', value: stats.documents_count, highlight: true },
          ]}
        />
      </div>
    </div>
  );
}

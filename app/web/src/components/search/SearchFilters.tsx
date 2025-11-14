import type { ContentTypeFilter } from '@hooks/useSearch';
import styles from './SearchFilters.module.css';

interface SearchFiltersProps {
  selectedType: ContentTypeFilter;
  onTypeChange: (type: ContentTypeFilter) => void;
  resultCounts?: {
    all: number;
    note: number;
    document: number;
    reminder: number;
    event: number;
  };
}

const FILTER_OPTIONS: { value: ContentTypeFilter; label: string; icon: string }[] = [
  { value: 'all', label: 'All', icon: '🔍' },
  { value: 'note', label: 'Notes', icon: '📝' },
  { value: 'document', label: 'Documents', icon: '📄' },
  { value: 'reminder', label: 'Reminders', icon: '⏰' },
  { value: 'event', label: 'Events', icon: '📅' },
];

export function SearchFilters({ selectedType, onTypeChange, resultCounts }: SearchFiltersProps) {
  return (
    <div className={styles.filters}>
      <div className={styles.filterLabel}>Filter by type:</div>
      <div className={styles.filterButtons}>
        {FILTER_OPTIONS.map(option => {
          const count = resultCounts?.[option.value] ?? 0;
          const isActive = selectedType === option.value;

          return (
            <button
              key={option.value}
              className={`${styles.filterButton} ${isActive ? styles.active : ''}`}
              onClick={() => onTypeChange(option.value)}
              aria-pressed={isActive}
            >
              <span className={styles.filterIcon}>{option.icon}</span>
              <span className={styles.filterText}>{option.label}</span>
              {resultCounts && count > 0 && (
                <span className={styles.filterCount}>({count})</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

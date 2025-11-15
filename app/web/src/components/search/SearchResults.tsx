import { useNavigate } from 'react-router-dom';
import type { SearchResult } from '@/types';
import styles from './SearchResults.module.css';

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
  isSearching: boolean;
  hasSearched: boolean;
}

interface GroupedResults {
  notes: SearchResult[];
  documents: SearchResult[];
  reminders: SearchResult[];
  events: SearchResult[];
}

const TYPE_LABELS: Record<string, string> = {
  note: 'Notes',
  document: 'Documents',
  reminder: 'Reminders',
  event: 'Events',
};

const TYPE_ICONS: Record<string, string> = {
  note: '📝',
  document: '📄',
  reminder: '⏰',
  event: '📅',
};

const TYPE_ROUTES: Record<string, string> = {
  note: '/notes',
  document: '/documents',
  reminder: '/reminders',
  event: '/calendar',
};

export function SearchResults({ results, query, isSearching, hasSearched }: SearchResultsProps) {
  const navigate = useNavigate();

  // Group results by type
  const groupedResults: GroupedResults = results.reduce(
    (acc, result) => {
      const type = result.type;
      if (type === 'note') acc.notes.push(result);
      else if (type === 'document') acc.documents.push(result);
      else if (type === 'reminder') acc.reminders.push(result);
      else if (type === 'event') acc.events.push(result);
      return acc;
    },
    { notes: [], documents: [], reminders: [], events: [] } as GroupedResults
  );

  // Highlight query terms in text
  const highlightText = (text: string, query: string): JSX.Element => {
    if (!query.trim()) {
      return <>{text}</>;
    }

    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return (
      <>
        {parts.map((part, index) =>
          part.toLowerCase() === query.toLowerCase() ? (
            <mark key={index} className={styles.highlight}>
              {part}
            </mark>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </>
    );
  };

  const handleResultClick = (result: SearchResult) => {
    const route = TYPE_ROUTES[result.type];
    // Navigate to the appropriate page, could add ID param for direct access
    navigate(route);
  };

  const renderResultItem = (result: SearchResult) => (
    <div
      key={result.id}
      className={styles.resultItem}
      onClick={() => handleResultClick(result)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          handleResultClick(result);
        }
      }}
    >
      <div className={styles.resultIcon}>{TYPE_ICONS[result.type]}</div>
      <div className={styles.resultContent}>
        <div className={styles.resultTitle}>
          {highlightText(result.title, query)}
        </div>
        <div className={styles.resultSnippet}>
          {highlightText(result.snippet, query)}
        </div>
        <div className={styles.resultMeta}>
          <span className={styles.resultType}>{TYPE_LABELS[result.type]}</span>
          {result.score && (
            <span className={styles.resultScore}>
              {Math.round(result.score * 100)}% match
            </span>
          )}
        </div>
      </div>
    </div>
  );

  const renderGroup = (type: keyof GroupedResults, results: SearchResult[]) => {
    if (results.length === 0) return null;

    return (
      <div key={type} className={styles.resultGroup}>
        <div className={styles.groupHeader}>
          <span className={styles.groupIcon}>{TYPE_ICONS[type]}</span>
          <span className={styles.groupTitle}>
            {TYPE_LABELS[type]} ({results.length})
          </span>
        </div>
        <div className={styles.groupItems}>
          {results.map(renderResultItem)}
        </div>
      </div>
    );
  };

  // Loading state
  if (isSearching) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <div className={styles.spinner}></div>
          <p>Searching...</p>
        </div>
      </div>
    );
  }

  // No search performed yet
  if (!hasSearched) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🔍</div>
          <h3>Search your workspace</h3>
          <p>Search across notes, documents, reminders, and calendar events.</p>
        </div>
      </div>
    );
  }

  // No results found
  if (results.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>🔍</div>
          <h3>No results found</h3>
          <p>Try different keywords or adjust your filters.</p>
        </div>
      </div>
    );
  }

  // Render grouped results
  return (
    <div className={styles.container}>
      <div className={styles.resultsHeader}>
        <h2>
          Found {results.length} result{results.length !== 1 ? 's' : ''}
        </h2>
      </div>
      <div className={styles.results}>
        {renderGroup('notes', groupedResults.notes)}
        {renderGroup('documents', groupedResults.documents)}
        {renderGroup('reminders', groupedResults.reminders)}
        {renderGroup('events', groupedResults.events)}
      </div>
    </div>
  );
}

import { useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSearch } from '@hooks/useSearch';
import { SearchFilters } from '@components/search/SearchFilters';
import { SearchResults } from '@components/search/SearchResults';
import styles from './SearchPage.module.css';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryParam = searchParams.get('q') || '';

  const {
    query,
    setQuery,
    contentType,
    setContentType,
    results,
    isSearching,
    hasSearched,
  } = useSearch({ initialQuery: queryParam });

  // Update URL when query changes
  useEffect(() => {
    if (query) {
      setSearchParams({ q: query });
    } else {
      setSearchParams({});
    }
  }, [query, setSearchParams]);

  // Calculate result counts by type
  const resultCounts = useMemo(() => {
    const counts = {
      all: results.length,
      note: 0,
      document: 0,
      reminder: 0,
      event: 0,
    };

    results.forEach(result => {
      counts[result.type]++;
    });

    return counts;
  }, [results]);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Search</h1>
        <div className={styles.searchBox}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search notes, documents, reminders, and events..."
            className={styles.searchInput}
            autoFocus
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className={styles.clearButton}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {hasSearched && (
        <SearchFilters
          selectedType={contentType}
          onTypeChange={setContentType}
          resultCounts={resultCounts}
        />
      )}

      <SearchResults
        results={results}
        query={query}
        isSearching={isSearching}
        hasSearched={hasSearched}
      />
    </div>
  );
}

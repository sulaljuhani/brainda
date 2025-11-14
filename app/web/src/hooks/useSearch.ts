import { useState, useEffect, useCallback } from 'react';
import { searchService } from '@services/searchService';
import type { SearchResult } from '@types/api';

export type ContentTypeFilter = 'all' | 'note' | 'document' | 'reminder' | 'event';

interface UseSearchOptions {
  initialQuery?: string;
  initialType?: ContentTypeFilter;
  limit?: number;
}

interface UseSearchReturn {
  query: string;
  setQuery: (query: string) => void;
  contentType: ContentTypeFilter;
  setContentType: (type: ContentTypeFilter) => void;
  results: SearchResult[];
  isSearching: boolean;
  error: string | null;
  search: () => Promise<void>;
  clearResults: () => void;
  hasSearched: boolean;
}

export function useSearch(options: UseSearchOptions = {}): UseSearchReturn {
  const {
    initialQuery = '',
    initialType = 'all',
    limit = 20,
  } = options;

  const [query, setQuery] = useState(initialQuery);
  const [contentType, setContentType] = useState<ContentTypeFilter>(initialType);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const search = useCallback(async () => {
    if (!query.trim()) {
      setResults([]);
      setHasSearched(false);
      return;
    }

    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await searchService.search(query, contentType, limit);
      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [query, contentType, limit]);

  const clearResults = useCallback(() => {
    setResults([]);
    setQuery('');
    setError(null);
    setHasSearched(false);
  }, []);

  // Auto-search when query or contentType changes (debounced)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (query.trim()) {
        search();
      }
    }, 300); // 300ms debounce

    return () => clearTimeout(timeoutId);
  }, [query, contentType]); // Only re-run when query or contentType changes

  return {
    query,
    setQuery,
    contentType,
    setContentType,
    results,
    isSearching,
    error,
    search,
    clearResults,
    hasSearched,
  };
}

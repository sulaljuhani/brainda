import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearch } from '@hooks/useSearch';
import type { SearchResult } from '@types/api';
import styles from './GlobalSearch.module.css';

interface GlobalSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

const TYPE_ICONS = {
  note: '📝',
  document: '📄',
  reminder: '⏰',
  event: '📅',
};

const TYPE_ROUTES = {
  note: '/notes',
  document: '/documents',
  reminder: '/reminders',
  event: '/calendar',
};

export function GlobalSearch({ isOpen, onClose }: GlobalSearchProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const { query, setQuery, results, isSearching } = useSearch({ limit: 10 });

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen, setQuery]);

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault();
      handleResultClick(results[selectedIndex]);
    }
  };

  const handleResultClick = (result: SearchResult) => {
    const route = TYPE_ROUTES[result.type];
    navigate(route);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.searchBox}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search notes, documents, reminders..."
            className={styles.searchInput}
          />
          <kbd className={styles.kbd}>ESC</kbd>
        </div>

        <div className={styles.results}>
          {isSearching && (
            <div className={styles.loading}>
              <div className={styles.spinner}></div>
              <span>Searching...</span>
            </div>
          )}

          {!isSearching && query && results.length === 0 && (
            <div className={styles.empty}>
              <span>No results found for "{query}"</span>
            </div>
          )}

          {!isSearching && !query && (
            <div className={styles.empty}>
              <span>Start typing to search...</span>
            </div>
          )}

          {!isSearching && results.length > 0 && (
            <div className={styles.resultsList}>
              {results.map((result, index) => (
                <div
                  key={result.id}
                  className={`${styles.resultItem} ${
                    index === selectedIndex ? styles.selected : ''
                  }`}
                  onClick={() => handleResultClick(result)}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <span className={styles.resultIcon}>{TYPE_ICONS[result.type]}</span>
                  <div className={styles.resultContent}>
                    <div className={styles.resultTitle}>{result.title}</div>
                    <div className={styles.resultSnippet}>{result.snippet}</div>
                  </div>
                  {index === selectedIndex && (
                    <kbd className={styles.enterKbd}>↵</kbd>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <div className={styles.shortcuts}>
            <span className={styles.shortcut}>
              <kbd>↑</kbd><kbd>↓</kbd> Navigate
            </span>
            <span className={styles.shortcut}>
              <kbd>↵</kbd> Open
            </span>
            <span className={styles.shortcut}>
              <kbd>ESC</kbd> Close
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserMenu } from '@components/auth/UserMenu';
import styles from './Header.module.css';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <div className={styles.logo} onClick={() => navigate('/')}>
          Brainda
        </div>

        <form className={styles.searchForm} onSubmit={handleSearch}>
          <div className={styles.searchBar}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search workspace..."
              className={styles.searchInput}
            />
          </div>
        </form>
      </div>

      <div className={styles.right}>
        <button className={styles.iconButton} aria-label="Notifications">
          🔔
          {/* Add badge if needed */}
        </button>

        <button className={styles.iconButton} aria-label="Settings">
          ⚙️
        </button>

        <UserMenu />
      </div>
    </header>
  );
}

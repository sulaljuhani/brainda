import { useNavigate, useLocation } from 'react-router-dom';
import { useRef, useEffect, useState } from 'react';
import { useSwipeGesture } from '@hooks/useSwipeGesture';
import { useIsMobileOrTablet } from '@hooks/useMediaQuery';
import { useChatConversations } from '@hooks/useChatConversations';
import { ConversationItem } from '../chat/ConversationItem';
import { NewConversationButton } from '../chat/NewConversationButton';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { UserMenu } from '@components/auth/UserMenu';
import {
  History,
  Search,
  MessageSquare,
  FileText,
  File,
  CheckSquare,
  Calendar as CalendarIcon,
  Bell,
  CalendarDays,
  Edit3,
  Settings
} from 'lucide-react';
import styles from './Sidebar.module.css';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  currentConversationId?: string | null;
  onConversationSelect?: (conversationId: string) => void;
  onNewConversation?: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, path: '/' },
  { id: 'notes', label: 'Notes', icon: FileText, path: '/notes' },
  { id: 'documents', label: 'Documents', icon: File, path: '/documents' },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare, path: '/tasks' },
  { id: 'events', label: 'Events', icon: CalendarIcon, path: '/events' },
  { id: 'reminders', label: 'Reminders', icon: Bell, path: '/reminders' },
  { id: 'calendar', label: 'Calendar', icon: CalendarDays, path: '/calendar' },
];

export function Sidebar({ collapsed, onToggle, currentConversationId, onConversationSelect, onNewConversation }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const sidebarRef = useRef<HTMLElement>(null);
  const isMobileOrTablet = useIsMobileOrTablet();
  const { conversations, isLoading, deleteConversation } = useChatConversations();
  const isChatPage = location.pathname === '/' || location.pathname === '/chat';
  const [searchQuery, setSearchQuery] = useState('');

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const handleDeleteConversation = async (conversationId: string) => {
    await deleteConversation(conversationId);
    // If deleted conversation was active, start a new one
    if (conversationId === currentConversationId && onNewConversation) {
      onNewConversation();
    }
  };

  // Add swipe left gesture to close sidebar on mobile
  useSwipeGesture(sidebarRef, {
    onSwipeLeft: () => {
      if (!collapsed && isMobileOrTablet) {
        onToggle();
      }
    },
  });

  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    if (!isMobileOrTablet || collapsed) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        onToggle();
      }
    };

    // Small delay to prevent immediate closing after opening
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [collapsed, onToggle, isMobileOrTablet]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <aside
      ref={sidebarRef}
      id="mobile-sidebar"
      className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}
    >
      {!collapsed && (
        <>
          <div className={styles.header}>
            <div className={styles.logo} onClick={() => navigate('/')}>
              Brainda
            </div>
            <button
              className={styles.iconButton}
              aria-label="Notifications"
            >
              <Bell size={20} />
            </button>
          </div>

          <div className={styles.searchSection}>
            <form onSubmit={handleSearch} className={styles.searchForm}>
              <div className={styles.searchBar}>
                <Search size={16} className={styles.searchIcon} />
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={styles.searchInput}
                />
              </div>
            </form>
            <button
              className={styles.newChatIconButton}
              onClick={() => {
                if (isChatPage && onNewConversation) {
                  onNewConversation();
                } else {
                  navigate('/?new=true');
                }
              }}
              aria-label="New conversation"
            >
              <Edit3 size={18} />
            </button>
          </div>
        </>
      )}

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`${styles.navItem} ${isActive(item.path) ? styles.active : ''}`}
              onClick={() => navigate(item.path)}
              aria-label={item.label}
            >
              <span className={styles.navIcon}>
                <Icon size={20} />
              </span>
              {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      <div className={styles.divider} />

      {!collapsed && (
        <div className={styles.chatHistorySection}>
          <div className={styles.sectionTitle}>
            <History size={16} />
            <span>Chat History</span>
          </div>

          <div className={styles.conversationList}>
            {isLoading && (
              <div className={styles.loadingContainer}>
                <LoadingSpinner />
              </div>
            )}

            {!isLoading && conversations.length === 0 && (
              <div className={styles.emptyState}>
                <p>No conversations yet</p>
              </div>
            )}

            {!isLoading && conversations.length > 0 && (
              <>
                {conversations.map((conversation) => (
                  <ConversationItem
                    key={conversation.id}
                    conversation={conversation}
                    isActive={conversation.id === currentConversationId}
                    onClick={() => {
                      if (onConversationSelect) {
                        onConversationSelect(conversation.id);
                      } else {
                        navigate(`/?conversation=${conversation.id}`);
                      }
                    }}
                    onDelete={handleDeleteConversation}
                  />
                ))}
              </>
            )}
          </div>
        </div>
      )}

      {!collapsed && (
        <div className={styles.userMenuSection}>
          <UserMenu />
        </div>
      )}
    </aside>
  );
}

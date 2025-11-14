import { useEffect, useState } from 'react';
import { Modal } from './Modal';
import { Keyboard } from 'lucide-react';
import './KeyboardShortcuts.css';

interface Shortcut {
  keys: string[];
  description: string;
  category: string;
}

const shortcuts: Shortcut[] = [
  { keys: ['?'], description: 'Show keyboard shortcuts', category: 'General' },
  { keys: ['Ctrl', 'K'], description: 'Quick search', category: 'General' },
  { keys: ['Escape'], description: 'Close modal/dialog', category: 'General' },

  { keys: ['G', 'C'], description: 'Go to Chat', category: 'Navigation' },
  { keys: ['G', 'N'], description: 'Go to Notes', category: 'Navigation' },
  { keys: ['G', 'R'], description: 'Go to Reminders', category: 'Navigation' },
  { keys: ['G', 'D'], description: 'Go to Documents', category: 'Navigation' },
  { keys: ['G', 'L'], description: 'Go to Calendar', category: 'Navigation' },
  { keys: ['G', 'S'], description: 'Go to Settings', category: 'Navigation' },

  { keys: ['N'], description: 'Create new note', category: 'Notes' },
  { keys: ['E'], description: 'Edit selected note', category: 'Notes' },
  { keys: ['Delete'], description: 'Delete selected note', category: 'Notes' },

  { keys: ['R'], description: 'Create new reminder', category: 'Reminders' },
  { keys: ['M'], description: 'Mark reminder as complete', category: 'Reminders' },

  { keys: ['U'], description: 'Upload document', category: 'Documents' },

  { keys: ['Enter'], description: 'Send message', category: 'Chat' },
  { keys: ['Shift', 'Enter'], description: 'New line in message', category: 'Chat' },
];

interface KeyboardShortcutsProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcuts({ isOpen, onClose }: KeyboardShortcutsProps) {
  const categories = Array.from(new Set(shortcuts.map((s) => s.category)));

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Keyboard Shortcuts" size="large">
      <div className="keyboard-shortcuts">
        {categories.map((category) => (
          <div key={category} className="keyboard-shortcuts-category">
            <h3 className="keyboard-shortcuts-category-title">{category}</h3>
            <div className="keyboard-shortcuts-list">
              {shortcuts
                .filter((s) => s.category === category)
                .map((shortcut, index) => (
                  <div key={index} className="keyboard-shortcut-item">
                    <div className="keyboard-shortcut-keys">
                      {shortcut.keys.map((key, keyIndex) => (
                        <span key={keyIndex}>
                          <kbd className="keyboard-shortcut-key">{key}</kbd>
                          {keyIndex < shortcut.keys.length - 1 && (
                            <span className="keyboard-shortcut-plus">+</span>
                          )}
                        </span>
                      ))}
                    </div>
                    <div className="keyboard-shortcut-description">{shortcut.description}</div>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}

export function useKeyboardShortcuts(onOpenHelp: () => void) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Show help modal on '?'
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target as HTMLElement;
        // Don't trigger if user is typing in an input
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
          return;
        }
        e.preventDefault();
        onOpenHelp();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onOpenHelp]);
}

export function KeyboardShortcutsButton() {
  const [isOpen, setIsOpen] = useState(false);

  useKeyboardShortcuts(() => setIsOpen(true));

  return (
    <>
      <button
        className="keyboard-shortcuts-button"
        onClick={() => setIsOpen(true)}
        title="Keyboard shortcuts (?)"
        aria-label="Show keyboard shortcuts"
      >
        <Keyboard size={20} />
      </button>
      <KeyboardShortcuts isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}

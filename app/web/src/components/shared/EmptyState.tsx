import { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';
import './EmptyState.css';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state-content">
        {Icon && (
          <div className="empty-state-icon">
            <Icon size={48} />
          </div>
        )}
        <h3 className="empty-state-title">{title}</h3>
        {description && <p className="empty-state-description">{description}</p>}
        {action && (
          <button className="empty-state-button" onClick={action.onClick}>
            {action.label}
          </button>
        )}
        {children}
      </div>
    </div>
  );
}

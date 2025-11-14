import './SkeletonScreen.css';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  variant?: 'text' | 'circular' | 'rectangular';
  className?: string;
}

export function Skeleton({ width, height, variant = 'rectangular', className = '' }: SkeletonProps) {
  const style = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  return (
    <div
      className={`skeleton skeleton--${variant} ${className}`}
      style={style}
      aria-busy="true"
      aria-live="polite"
    />
  );
}

// Pre-built skeleton layouts for common use cases

export function SkeletonNote() {
  return (
    <div className="skeleton-note">
      <Skeleton variant="text" width="70%" height={24} />
      <Skeleton variant="text" width="100%" height={16} />
      <Skeleton variant="text" width="100%" height={16} />
      <Skeleton variant="text" width="40%" height={16} />
      <div className="skeleton-note-footer">
        <Skeleton variant="text" width={80} height={14} />
        <Skeleton variant="text" width={60} height={14} />
      </div>
    </div>
  );
}

export function SkeletonChatMessage() {
  return (
    <div className="skeleton-chat-message">
      <Skeleton variant="circular" width={32} height={32} />
      <div className="skeleton-chat-content">
        <Skeleton variant="text" width="100%" height={16} />
        <Skeleton variant="text" width="90%" height={16} />
        <Skeleton variant="text" width="60%" height={16} />
      </div>
    </div>
  );
}

export function SkeletonReminder() {
  return (
    <div className="skeleton-reminder">
      <Skeleton variant="rectangular" width={40} height={40} />
      <div className="skeleton-reminder-content">
        <Skeleton variant="text" width="60%" height={18} />
        <Skeleton variant="text" width="40%" height={14} />
      </div>
    </div>
  );
}

export function SkeletonDocument() {
  return (
    <div className="skeleton-document">
      <Skeleton variant="rectangular" width={48} height={48} />
      <div className="skeleton-document-content">
        <Skeleton variant="text" width="70%" height={18} />
        <Skeleton variant="text" width="50%" height={14} />
        <Skeleton variant="text" width="30%" height={14} />
      </div>
    </div>
  );
}

export function SkeletonCalendarEvent() {
  return (
    <div className="skeleton-calendar-event">
      <div className="skeleton-calendar-time">
        <Skeleton variant="text" width={60} height={14} />
      </div>
      <div className="skeleton-calendar-details">
        <Skeleton variant="text" width="80%" height={16} />
        <Skeleton variant="text" width="50%" height={14} />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton-list-item">
          <Skeleton variant="text" width="100%" height={20} />
        </div>
      ))}
    </div>
  );
}

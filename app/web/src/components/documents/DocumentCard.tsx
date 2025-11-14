import { useState } from 'react';
import type { Document } from '../../types/api';
import { formatDistanceToNow } from 'date-fns';
import styles from './DocumentCard.module.css';

interface DocumentCardProps {
  document: Document;
  onDelete: (id: string) => Promise<void>;
  onView: (document: Document) => void;
}

export function DocumentCard({ document, onDelete, onView }: DocumentCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getFileIcon = (contentType: string): string => {
    if (contentType.includes('pdf')) return '📕';
    if (contentType.includes('word') || contentType.includes('doc')) return '📘';
    if (contentType.includes('text')) return '📄';
    if (contentType.includes('markdown')) return '📝';
    return '📄';
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(document.id);
    } catch (error) {
      console.error('Failed to delete document:', error);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const timeAgo = formatDistanceToNow(new Date(document.created_at), { addSuffix: true });

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div className={styles.fileIcon}>{getFileIcon(document.content_type)}</div>
        <div className={styles.fileInfo}>
          <h3 className={styles.filename}>{document.filename}</h3>
          <div className={styles.metadata}>
            <span className={styles.fileSize}>{formatFileSize(document.size_bytes)}</span>
            <span className={styles.separator}>•</span>
            <span className={styles.uploadDate}>{timeAgo}</span>
          </div>
        </div>
      </div>

      <div className={styles.cardActions}>
        <button
          className={styles.actionButton}
          onClick={() => onView(document)}
          aria-label="View document"
        >
          <span className={styles.actionIcon}>👁️</span>
          <span className={styles.actionLabel}>View</span>
        </button>

        {!showDeleteConfirm ? (
          <button
            className={`${styles.actionButton} ${styles.deleteButton}`}
            onClick={() => setShowDeleteConfirm(true)}
            aria-label="Delete document"
          >
            <span className={styles.actionIcon}>🗑️</span>
            <span className={styles.actionLabel}>Delete</span>
          </button>
        ) : (
          <div className={styles.deleteConfirm}>
            <button
              className={styles.confirmButton}
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Confirm'}
            </button>
            <button
              className={styles.cancelButton}
              onClick={() => setShowDeleteConfirm(false)}
              disabled={isDeleting}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

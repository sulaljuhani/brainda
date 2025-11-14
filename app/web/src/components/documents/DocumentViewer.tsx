import { useEffect } from 'react';
import type { Document } from '../../types/api';
import styles from './DocumentViewer.module.css';

interface DocumentViewerProps {
  document: Document | null;
  isOpen: boolean;
  onClose: () => void;
}

export function DocumentViewer({ document: doc, isOpen, onClose }: DocumentViewerProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      window.document.addEventListener('keydown', handleEscape);
      window.document.body.style.overflow = 'hidden';
    }

    return () => {
      window.document.removeEventListener('keydown', handleEscape);
      window.document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !doc) return null;

  const isPDF = doc.content_type.includes('pdf');
  const isText =
    doc.content_type.includes('text') ||
    doc.content_type.includes('markdown');

  // Get the API base URL
  const apiBaseUrl = import.meta.env.VITE_API_URL || '';
  const apiBasePath = import.meta.env.VITE_API_BASE_PATH || '/api/v1';

  // Construct the document URL
  const documentUrl = `${apiBaseUrl}${apiBasePath}/documents/${doc.id}/content`;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <h2 className={styles.title}>{doc.filename}</h2>
            <div className={styles.metadata}>
              {doc.content_type}
            </div>
          </div>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className={styles.content}>
          {isPDF ? (
            <div className={styles.pdfContainer}>
              <iframe
                src={documentUrl}
                className={styles.pdfViewer}
                title={doc.filename}
              />
              <div className={styles.pdfFallback}>
                <p>PDF preview not supported in your browser.</p>
                <a
                  href={documentUrl}
                  download={doc.filename}
                  className={styles.downloadLink}
                >
                  Download PDF
                </a>
              </div>
            </div>
          ) : isText ? (
            <div className={styles.textContainer}>
              <iframe
                src={documentUrl}
                className={styles.textViewer}
                title={doc.filename}
              />
            </div>
          ) : (
            <div className={styles.unsupportedContainer}>
              <div className={styles.unsupportedIcon}>📄</div>
              <p className={styles.unsupportedText}>
                Preview not available for this file type
              </p>
              <p className={styles.unsupportedSubtext}>
                {doc.content_type}
              </p>
              <a
                href={documentUrl}
                download={doc.filename}
                className={styles.downloadButton}
              >
                Download File
              </a>
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <a
            href={documentUrl}
            download={doc.filename}
            className={styles.downloadButtonFooter}
          >
            📥 Download
          </a>
          <button className={styles.closeButtonFooter} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

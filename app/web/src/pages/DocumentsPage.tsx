import { useState } from 'react';
import { useDocuments } from '@hooks/useDocuments';
import { DocumentUpload } from '@components/documents/DocumentUpload';
import { DocumentCard } from '@components/documents/DocumentCard';
import { DocumentViewer } from '@components/documents/DocumentViewer';
import type { Document } from '../types/api';
import styles from './DocumentsPage.module.css';

export default function DocumentsPage() {
  const { documents, loading, error, uploadDocument, deleteDocument } = useDocuments();
  const [searchQuery, setSearchQuery] = useState('');
  const [viewingDocument, setViewingDocument] = useState<Document | null>(null);
  const [filterType, setFilterType] = useState<string>('all');

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch = doc.filename
      .toLowerCase()
      .includes(searchQuery.toLowerCase());

    if (filterType === 'all') return matchesSearch;

    const matchesType =
      (filterType === 'pdf' && doc.content_type.includes('pdf')) ||
      (filterType === 'text' &&
        (doc.content_type.includes('text') ||
          doc.content_type.includes('markdown'))) ||
      (filterType === 'doc' &&
        (doc.content_type.includes('word') ||
          doc.content_type.includes('doc')));

    return matchesSearch && matchesType;
  });

  const handleUpload = async (file: File) => {
    await uploadDocument(file);
  };

  const handleDelete = async (id: string) => {
    await deleteDocument(id);
  };

  const handleView = (document: Document) => {
    setViewingDocument(document);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h1 className={styles.title}>Documents</h1>
          <p className={styles.subtitle}>
            Upload and manage your document library
          </p>
        </div>
      </div>

      <div className={styles.uploadSection}>
        <DocumentUpload onUpload={handleUpload} />
      </div>

      <div className={styles.controlsSection}>
        <div className={styles.searchBar}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className={styles.clearButton}
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        <div className={styles.filterButtons}>
          <button
            className={`${styles.filterButton} ${filterType === 'all' ? styles.active : ''}`}
            onClick={() => setFilterType('all')}
          >
            All
          </button>
          <button
            className={`${styles.filterButton} ${filterType === 'pdf' ? styles.active : ''}`}
            onClick={() => setFilterType('pdf')}
          >
            PDF
          </button>
          <button
            className={`${styles.filterButton} ${filterType === 'text' ? styles.active : ''}`}
            onClick={() => setFilterType('text')}
          >
            Text
          </button>
          <button
            className={`${styles.filterButton} ${filterType === 'doc' ? styles.active : ''}`}
            onClick={() => setFilterType('doc')}
          >
            Documents
          </button>
        </div>
      </div>

      <div className={styles.documentsSection}>
        {loading && (
          <div className={styles.loading}>
            <div className={styles.spinner}></div>
            <p>Loading documents...</p>
          </div>
        )}

        {error && (
          <div className={styles.error}>
            <span className={styles.errorIcon}>⚠️</span>
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && filteredDocuments.length === 0 && (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>📄</div>
            <p className={styles.emptyText}>
              {searchQuery || filterType !== 'all'
                ? 'No documents match your search'
                : 'No documents yet'}
            </p>
            <p className={styles.emptySubtext}>
              {searchQuery || filterType !== 'all'
                ? 'Try adjusting your filters'
                : 'Upload your first document to get started'}
            </p>
          </div>
        )}

        {!loading && !error && filteredDocuments.length > 0 && (
          <>
            <div className={styles.documentsHeader}>
              <span className={styles.documentsCount}>
                {filteredDocuments.length} document{filteredDocuments.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className={styles.documentsGrid}>
              {filteredDocuments.map((document) => (
                <DocumentCard
                  key={document.id}
                  document={document}
                  onDelete={handleDelete}
                  onView={handleView}
                />
              ))}
            </div>
          </>
        )}
      </div>

      <DocumentViewer
        document={viewingDocument}
        isOpen={viewingDocument !== null}
        onClose={() => setViewingDocument(null)}
      />
    </div>
  );
}

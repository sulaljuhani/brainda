import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import styles from './DocumentUpload.module.css';

interface UploadProgress {
  filename: string;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
}

interface DocumentUploadProps {
  onUploadComplete?: () => void;
  onUpload: (file: File) => Promise<any>;
}

export function DocumentUpload({ onUploadComplete, onUpload }: DocumentUploadProps) {
  const [uploads, setUploads] = useState<UploadProgress[]>([]);

  const handleUpload = useCallback(
    async (file: File) => {
      const uploadItem: UploadProgress = {
        filename: file.name,
        progress: 0,
        status: 'uploading',
      };

      setUploads((prev) => [...prev, uploadItem]);

      try {
        // Simulate progress since we don't have real progress tracking
        const progressInterval = setInterval(() => {
          setUploads((prev) =>
            prev.map((item) =>
              item.filename === file.name && item.status === 'uploading'
                ? { ...item, progress: Math.min(item.progress + 10, 90) }
                : item
            )
          );
        }, 200);

        await onUpload(file);

        clearInterval(progressInterval);

        setUploads((prev) =>
          prev.map((item) =>
            item.filename === file.name
              ? { ...item, progress: 100, status: 'completed' }
              : item
          )
        );

        // Remove completed upload after 3 seconds
        setTimeout(() => {
          setUploads((prev) => prev.filter((item) => item.filename !== file.name));
        }, 3000);

        onUploadComplete?.();
      } catch (error) {
        setUploads((prev) =>
          prev.map((item) =>
            item.filename === file.name
              ? {
                  ...item,
                  status: 'error',
                  error: error instanceof Error ? error.message : 'Upload failed',
                }
              : item
          )
        );
      }
    },
    [onUpload, onUploadComplete]
  );

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      acceptedFiles.forEach((file) => {
        handleUpload(file);
      });
    },
    [handleUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  });

  return (
    <div className={styles.container}>
      <div
        {...getRootProps()}
        className={`${styles.dropzone} ${isDragActive ? styles.active : ''}`}
      >
        <input {...getInputProps()} />
        <div className={styles.dropzoneContent}>
          <div className={styles.uploadIcon}>📤</div>
          {isDragActive ? (
            <p className={styles.dropzoneText}>Drop files here...</p>
          ) : (
            <>
              <p className={styles.dropzoneText}>
                Drag & drop files here, or click to select
              </p>
              <p className={styles.dropzoneSubtext}>
                Supports PDF, TXT, MD, DOC, DOCX
              </p>
            </>
          )}
        </div>
      </div>

      {uploads.length > 0 && (
        <div className={styles.uploadsList}>
          <h3 className={styles.uploadsTitle}>Uploads</h3>
          {uploads.map((upload) => (
            <div key={upload.filename} className={styles.uploadItem}>
              <div className={styles.uploadInfo}>
                <div className={styles.uploadFilename}>{upload.filename}</div>
                {upload.status === 'uploading' && (
                  <div className={styles.uploadProgress}>
                    <div
                      className={styles.uploadProgressBar}
                      style={{ width: `${upload.progress}%` }}
                    />
                  </div>
                )}
                {upload.status === 'completed' && (
                  <div className={styles.uploadStatus}>✓ Completed</div>
                )}
                {upload.status === 'error' && (
                  <div className={styles.uploadError}>✗ {upload.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

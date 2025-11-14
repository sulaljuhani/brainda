import { useState, useEffect } from 'react';
import { documentsService } from '@services/documentsService';
import type { Document, UploadDocumentResponse } from '@types/*';

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await documentsService.getAll();
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const uploadDocument = async (file: File): Promise<UploadDocumentResponse> => {
    const response = await documentsService.upload(file);
    // Refresh the documents list after upload
    await fetchDocuments();
    return response;
  };

  const deleteDocument = async (id: string) => {
    await documentsService.delete(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  return {
    documents,
    loading,
    error,
    uploadDocument,
    deleteDocument,
    refetch: fetchDocuments,
  };
}

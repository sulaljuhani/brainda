'use client';

import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface Document {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
}

export default function DocumentList() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDocuments();
  }, []);

  async function fetchDocuments() {
    const token = localStorage.getItem('session_token') ?? localStorage.getItem('api_token');
    const response = await fetch('/api/v1/documents', {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    setDocuments(data);
    setLoading(false);
  }

  async function deleteDocument(id: string) {
    if (!confirm('Delete this document?')) return;
    const token = localStorage.getItem('session_token') ?? localStorage.getItem('api_token');
    await fetch(`/api/v1/documents/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    fetchDocuments();
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) return <div>Loading documents...</div>;

  if (!documents.length) {
    return <p className="text-gray-500">No documents uploaded yet.</p>;
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div key={doc.id} className="border p-4 rounded-lg">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <h3 className="font-semibold">{doc.filename}</h3>
              <div className="text-sm text-gray-600 space-x-4 mt-1">
                <span>{formatBytes(doc.size_bytes)}</span>
                <span>{doc.mime_type}</span>
                <span>
                  {formatDistanceToNow(new Date(doc.created_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
              <div className="mt-2">
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    doc.status === 'indexed'
                      ? 'bg-green-100 text-green-800'
                      : doc.status === 'processing'
                      ? 'bg-yellow-100 text-yellow-800'
                      : doc.status === 'failed'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {doc.status}
                </span>
              </div>
            </div>
            <button
              onClick={() => deleteDocument(doc.id)}
              className="text-sm px-3 py-1 bg-red-100 hover:bg-red-200 rounded"
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

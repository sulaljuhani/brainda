'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

interface UploadResult {
  success: boolean;
  job_id?: string;
  document_id?: string;
  message?: string;
  deduplicated?: boolean;
}

export default function DocumentUpload() {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');

  const getAuthToken = useCallback(
    () => localStorage.getItem('session_token') ?? localStorage.getItem('api_token'),
    [],
  );

  const pollJobStatus = useCallback(async (jobId: string) => {
    const token = getAuthToken();
    const maxAttempts = 60;
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await fetch(`/api/v1/jobs/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) return;

        const job = await response.json();
        setJobStatus(job.status);

        if (job.status === 'completed') {
          setJobStatus('✓ Document indexed and searchable');
          return;
        }

        if (job.status === 'failed') {
          setJobStatus(`✗ Failed: ${job.error_message}`);
          return;
        }

        attempts += 1;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        }
      } catch (error) {
        console.error('Failed to poll job status', error);
      }
    };

    poll();
  }, [getAuthToken]);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    setUploading(true);
    setResult(null);
    setJobStatus('');

    const formData = new FormData();
    formData.append('file', file);

    const token = getAuthToken();

    try {
      const response = await fetch('/api/v1/ingest', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await response.json();
      setResult(data);

      if (data.success && data.job_id) {
        pollJobStatus(data.job_id);
      }
    } catch (error) {
      console.error('Upload failed:', error);
      setResult({ success: false, message: 'Upload failed' });
    } finally {
      setUploading(false);
    }
  }, [getAuthToken, pollJobStatus]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/markdown': ['.md'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
          isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
        }`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <p className="text-gray-600">Uploading...</p>
        ) : isDragActive ? (
          <p className="text-blue-600">Drop the document here</p>
        ) : (
          <>
            <p className="text-gray-600">Drag & drop a document here, or click to select</p>
            <p className="text-sm text-gray-400 mt-2">
              Supported: PDF, DOCX, TXT, MD (max 50MB)
            </p>
          </>
        )}
      </div>

      {result && (
        <div className={`p-4 rounded ${result.success ? 'bg-green-50' : 'bg-red-50'}`}>
          <p className={result.success ? 'text-green-800' : 'text-red-800'}>
            {result.message ||
              (result.success
                ? result.deduplicated
                  ? 'Document already ingested'
                  : 'Upload successful'
                : 'Upload failed')}
          </p>
          {jobStatus && (
            <p className="text-sm text-gray-600 mt-2">Status: {jobStatus}</p>
          )}
        </div>
      )}
    </div>
  );
}

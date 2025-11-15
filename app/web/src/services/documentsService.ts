import { api } from './api';
import type { Document, UploadDocumentResponse, JobStatus } from '@/types';

export const documentsService = {
  getAll: () => api.get<Document[]>('/documents'),

  upload: (file: File) =>
    api.uploadFile('/ingest', file) as Promise<UploadDocumentResponse>,

  getJobStatus: (jobId: string) => api.get<JobStatus>(`/jobs/${jobId}`),

  delete: (id: string) => api.delete<void>(`/documents/${id}`),
};

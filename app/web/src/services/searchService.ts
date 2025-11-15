import { api } from './api';
import type { SearchResponse } from '@/types';

export type ContentTypeFilter = 'all' | 'note' | 'document' | 'reminder' | 'event';

export const searchService = {
  search: (query: string, contentType: ContentTypeFilter = 'all', limit = 20) => {
    const params = new URLSearchParams({
      q: query.trim(),
      limit: limit.toString(),
    });

    // Only add content_type if it's not 'all'
    if (contentType !== 'all') {
      params.append('content_type', contentType);
    }

    return api.get<SearchResponse>(`/search?${params.toString()}`);
  },
};

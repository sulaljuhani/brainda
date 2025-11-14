import { api } from './api';
import type { SearchResponse } from '@types/*';

export const searchService = {
  search: (query: string, limit = 20) =>
    api.get<SearchResponse>(
      `/search?query=${encodeURIComponent(query)}&limit=${limit}`
    ),
};

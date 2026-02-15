import { apiFetch } from './client';

export interface SearchResults {
  query: string;
  results: {
    activities?: any[];
    calendar?: any[];
    agents?: any[];
    skills?: any[];
  };
}

export function globalSearch(q: string, type = 'all'): Promise<SearchResults> {
  return apiFetch(`/api/search?q=${encodeURIComponent(q)}&type=${type}`);
}

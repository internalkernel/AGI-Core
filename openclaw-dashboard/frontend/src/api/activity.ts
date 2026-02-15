import { apiFetch } from './client';

export interface ActivityItem {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string | null;
  actor: string | null;
  timestamp: string;
  details: Record<string, any> | null;
  status: string | null;
}

export interface ActivityParams {
  entity_type?: string;
  event_type?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export function fetchActivities(params: ActivityParams = {}): Promise<ActivityItem[]> {
  const qs = new URLSearchParams();
  if (params.entity_type) qs.set('entity_type', params.entity_type);
  if (params.event_type) qs.set('event_type', params.event_type);
  if (params.since) qs.set('since', params.since);
  if (params.until) qs.set('until', params.until);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  return apiFetch(`/api/activity?${qs}`);
}

export function fetchRecentActivities(): Promise<ActivityItem[]> {
  return apiFetch('/api/activity/recent');
}

export function fetchActivityStats(): Promise<Record<string, number>> {
  return apiFetch('/api/activity/stats');
}

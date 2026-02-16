import { apiFetch, apiPost, apiPut, apiDelete } from './client';

export interface CalendarEvent {
  id: string;
  title: string;
  description?: string | null;
  start_time: string;
  end_time?: string | null;
  all_day: boolean;
  source: 'dashboard' | 'google';
  agent?: string | null;
}

export interface CalendarEventCreate {
  title: string;
  description?: string;
  start_time: string;
  end_time?: string;
  all_day?: boolean;
  agent?: string;
  sync_to_google?: boolean;
}

export function fetchCalendarEvents(start?: string, end?: string, include_google = true): Promise<CalendarEvent[]> {
  const qs = new URLSearchParams();
  if (start) qs.set('start', start);
  if (end) qs.set('end', end);
  qs.set('include_google', String(include_google));
  return apiFetch(`/api/calendar/events?${qs}`);
}

export function createCalendarEvent(data: CalendarEventCreate) {
  return apiPost<{ id: string }>('/api/calendar/events', data);
}

export function updateCalendarEvent(id: string, data: Partial<CalendarEventCreate>) {
  return apiPut<{ message: string }>(`/api/calendar/events/${id}`, data);
}

export function deleteCalendarEvent(id: string) {
  return apiDelete<{ message: string }>(`/api/calendar/events/${id}`);
}

export function fetchCalendarSettings(): Promise<{ google_calendar_enabled: boolean }> {
  return apiFetch('/api/calendar/settings');
}

export function updateCalendarSettings(settings: { google_calendar_enabled: boolean }) {
  return apiPut<{ message: string }>('/api/calendar/settings', settings);
}

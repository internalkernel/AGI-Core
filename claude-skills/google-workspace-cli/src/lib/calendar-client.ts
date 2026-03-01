import { google, calendar_v3 } from 'googleapis';
import type { OAuth2Client } from 'google-auth-library';
import type { Calendar, CalendarEvent } from '../types/index.js';

export class CalendarClient {
  private calendar: calendar_v3.Calendar;

  constructor(auth: OAuth2Client) {
    this.calendar = google.calendar({ version: 'v3', auth });
  }

  /**
   * List all calendars for the authenticated user
   */
  async listCalendars(): Promise<Calendar[]> {
    const response = await this.calendar.calendarList.list();
    const calendars = response.data.items || [];

    return calendars.map(cal => ({
      id: cal.id || '',
      summary: cal.summary || '',
      description: cal.description ?? undefined,
      primary: cal.primary || false,
      accessRole: cal.accessRole || '',
    }));
  }

  /**
   * List upcoming events
   * @param options.calendarId - Calendar ID (defaults to 'primary')
   * @param options.days - Number of days to look ahead (defaults to 7)
   * @param options.maxResults - Maximum number of events to return (defaults to 10)
   */
  async listEvents(options: {
    calendarId?: string;
    days?: number;
    maxResults?: number;
  } = {}): Promise<CalendarEvent[]> {
    const calendarId = options.calendarId || 'primary';
    const days = options.days || 7;
    const maxResults = options.maxResults || 10;

    const timeMin = new Date().toISOString();
    const timeMax = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();

    const response = await this.calendar.events.list({
      calendarId,
      timeMin,
      timeMax,
      maxResults,
      singleEvents: true,
      orderBy: 'startTime',
    });

    const events = response.data.items || [];
    return events.map(event => this.parseEvent(event, calendarId));
  }

  /**
   * Search events by text query
   * @param query - Search query text
   * @param options.calendarId - Calendar ID (defaults to 'primary')
   * @param options.days - Number of days to search (defaults to 30)
   */
  async search(
    query: string,
    options: {
      calendarId?: string;
      days?: number;
    } = {}
  ): Promise<CalendarEvent[]> {
    const calendarId = options.calendarId || 'primary';
    const days = options.days || 30;

    const timeMin = new Date().toISOString();
    const timeMax = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();

    const response = await this.calendar.events.list({
      calendarId,
      q: query,
      timeMin,
      timeMax,
      singleEvents: true,
      orderBy: 'startTime',
    });

    const events = response.data.items || [];
    return events.map(event => this.parseEvent(event, calendarId));
  }

  /**
   * Create a new calendar event
   * @param options.calendarId - Calendar ID (defaults to 'primary')
   * @param options.summary - Event title/summary
   * @param options.start - Start date/time (flexible format)
   * @param options.end - End date/time (optional, defaults to start + 1 hour)
   * @param options.description - Event description
   * @param options.location - Event location
   * @param options.attendees - Array of attendee email addresses
   * @returns Event ID
   */
  async createEvent(options: {
    calendarId?: string;
    summary: string;
    start: string;
    end?: string;
    description?: string;
    location?: string;
    attendees?: string[];
  }): Promise<string> {
    const calendarId = options.calendarId || 'primary';
    const startDateTime = this.parseDateTime(options.start);

    // Default end time is 1 hour after start
    const endDateTime = options.end
      ? this.parseDateTime(options.end)
      : new Date(new Date(startDateTime).getTime() + 60 * 60 * 1000).toISOString();

    const event: calendar_v3.Schema$Event = {
      summary: options.summary,
      description: options.description,
      location: options.location,
      start: {
        dateTime: startDateTime,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      },
      end: {
        dateTime: endDateTime,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      },
    };

    if (options.attendees && options.attendees.length > 0) {
      event.attendees = options.attendees.map(email => ({ email }));
    }

    const response = await this.calendar.events.insert({
      calendarId,
      requestBody: event,
    });

    return response.data.id || '';
  }

  /**
   * Update an existing calendar event
   * @param eventId - Event ID to update
   * @param options.calendarId - Calendar ID (defaults to 'primary')
   * @param options.summary - New event title
   * @param options.start - New start date/time
   * @param options.end - New end date/time
   * @param options.description - New description
   * @param options.location - New location
   */
  async updateEvent(
    eventId: string,
    options: {
      calendarId?: string;
      summary?: string;
      start?: string;
      end?: string;
      description?: string;
      location?: string;
    } = {}
  ): Promise<void> {
    const calendarId = options.calendarId || 'primary';

    // Fetch the existing event first
    const existingEvent = await this.calendar.events.get({
      calendarId,
      eventId,
    });

    const event: calendar_v3.Schema$Event = {
      ...existingEvent.data,
    };

    // Update only the fields that are provided
    if (options.summary !== undefined) {
      event.summary = options.summary;
    }
    if (options.description !== undefined) {
      event.description = options.description;
    }
    if (options.location !== undefined) {
      event.location = options.location;
    }
    if (options.start !== undefined) {
      event.start = {
        dateTime: this.parseDateTime(options.start),
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
    }
    if (options.end !== undefined) {
      event.end = {
        dateTime: this.parseDateTime(options.end),
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };
    }

    await this.calendar.events.update({
      calendarId,
      eventId,
      requestBody: event,
    });
  }

  /**
   * Delete a calendar event
   * @param eventId - Event ID to delete
   * @param calendarId - Calendar ID (defaults to 'primary')
   */
  async deleteEvent(eventId: string, calendarId?: string): Promise<void> {
    await this.calendar.events.delete({
      calendarId: calendarId || 'primary',
      eventId,
    });
  }

  /**
   * Parse a Google Calendar API event response into a CalendarEvent
   * @param event - Raw event from Google Calendar API
   * @param calendarId - Calendar ID the event belongs to
   */
  parseEvent(event: calendar_v3.Schema$Event, calendarId: string): CalendarEvent {
    const start = event.start?.dateTime || event.start?.date || '';
    const end = event.end?.dateTime || event.end?.date || '';
    const attendees = event.attendees?.map(a => a.email || '') || [];

    return {
      id: event.id || '',
      calendarId,
      summary: event.summary || '(No title)',
      description: event.description ?? undefined,
      start,
      end,
      location: event.location ?? undefined,
      attendees: attendees.filter(email => email !== ''),
      status: event.status || 'confirmed',
    };
  }

  /**
   * Parse flexible date/time input into ISO 8601 string
   * Supports formats like:
   * - ISO 8601: "2025-01-15T10:00:00Z"
   * - Date + time: "2025-01-15 10:00"
   * - Relative: "tomorrow 2pm", "today 3:30pm"
   *
   * @param input - Flexible date/time string
   * @returns ISO 8601 date/time string
   */
  parseDateTime(input: string): string {
    // If already ISO 8601 format, return as-is
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(input)) {
      return new Date(input).toISOString();
    }

    // Handle relative dates like "today", "tomorrow"
    let baseDate = new Date();
    let timeStr = input.trim();

    if (timeStr.toLowerCase().startsWith('today')) {
      timeStr = timeStr.slice(5).trim();
    } else if (timeStr.toLowerCase().startsWith('tomorrow')) {
      baseDate.setDate(baseDate.getDate() + 1);
      timeStr = timeStr.slice(8).trim();
    }

    // Handle "YYYY-MM-DD HH:MM" format
    const dateTimeMatch = timeStr.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})$/);
    if (dateTimeMatch) {
      const [, datePart, hours, minutes] = dateTimeMatch;
      return new Date(`${datePart}T${hours.padStart(2, '0')}:${minutes}:00`).toISOString();
    }

    // Handle time-only formats like "2pm", "3:30pm", "14:00"
    const timeOnlyMatch = timeStr.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/i);
    if (timeOnlyMatch) {
      const [, hoursStr, minutesStr = '0', meridian] = timeOnlyMatch;
      let hours = parseInt(hoursStr, 10);
      const minutes = parseInt(minutesStr, 10);

      if (meridian) {
        const isPM = meridian.toLowerCase() === 'pm';
        if (isPM && hours < 12) hours += 12;
        if (!isPM && hours === 12) hours = 0;
      }

      baseDate.setHours(hours, minutes, 0, 0);
      return baseDate.toISOString();
    }

    // If all else fails, try to parse directly
    const parsed = new Date(input);
    if (isNaN(parsed.getTime())) {
      throw new Error(`Unable to parse date/time: ${input}`);
    }

    return parsed.toISOString();
  }
}

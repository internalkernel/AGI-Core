import { Command } from 'commander';
import { CalendarClient } from '../lib/calendar-client.js';
import { getAuthenticatedClient } from '../lib/auth.js';
import { getActiveProfile } from '../lib/config.js';
import {
  formatCalendarList,
  formatEventList,
  print,
  printSuccess,
  printError,
} from '../lib/output.js';
import type { GlobalOptions } from '../types/index.js';

/**
 * Register all calendar subcommands
 */
export function registerCalendarCommands(program: Command): void {
  const calendar = program
    .command('calendar')
    .description('Manage Google Calendar events and calendars');

  // calendar list
  calendar
    .command('list')
    .description('List all calendars')
    .action(async (options: GlobalOptions) => {
      try {
        const profileName = getActiveProfile(options.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new CalendarClient(auth);

        const calendars = await client.listCalendars();
        const format = options.format || 'table';
        const output = formatCalendarList(calendars, format);
        print(output);
      } catch (error) {
        printError(
          'Error listing calendars: ' +
            (error instanceof Error ? error.message : String(error))
        );
        process.exit(1);
      }
    });

  // calendar events
  calendar
    .command('events')
    .description('List upcoming events')
    .option('--days <number>', 'Number of days to look ahead', '7')
    .option('--calendar <id>', 'Calendar ID to query', 'primary')
    .option('--limit <number>', 'Maximum number of events to return', '10')
    .action(
      async (options: GlobalOptions & { days: string; calendar: string; limit: string }) => {
        try {
          const profileName = getActiveProfile(options.profile);
          const auth = await getAuthenticatedClient(profileName);
          const client = new CalendarClient(auth);

          const events = await client.listEvents({
            calendarId: options.calendar,
            days: parseInt(options.days, 10),
            maxResults: parseInt(options.limit, 10),
          });

          const format = options.format || 'table';
          const output = formatEventList(events, format);
          print(output);
        } catch (error) {
          printError(
            'Error listing events: ' +
              (error instanceof Error ? error.message : String(error))
          );
          process.exit(1);
        }
      }
    );

  // calendar search
  calendar
    .command('search <query>')
    .description('Search events by text query')
    .option('--days <number>', 'Number of days to search', '30')
    .option('--calendar <id>', 'Calendar ID to search', 'primary')
    .action(
      async (
        query: string,
        options: GlobalOptions & { days: string; calendar: string }
      ) => {
        try {
          const profileName = getActiveProfile(options.profile);
          const auth = await getAuthenticatedClient(profileName);
          const client = new CalendarClient(auth);

          const events = await client.search(query, {
            calendarId: options.calendar,
            days: parseInt(options.days, 10),
          });

          const format = options.format || 'table';
          const output = formatEventList(events, format);
          print(output);
        } catch (error) {
          printError(
            'Error searching events: ' +
              (error instanceof Error ? error.message : String(error))
          );
          process.exit(1);
        }
      }
    );

  // calendar create
  calendar
    .command('create <title>')
    .description('Create a new calendar event')
    .requiredOption('--start <datetime>', 'Event start date/time (e.g., "2025-01-15 10:00", "tomorrow 2pm")')
    .option('--end <datetime>', 'Event end date/time (defaults to start + 1 hour)')
    .option('--calendar <id>', 'Calendar ID', 'primary')
    .option('--description <text>', 'Event description')
    .option('--location <place>', 'Event location')
    .option('--attendees <emails>', 'Comma-separated list of attendee email addresses')
    .action(
      async (
        title: string,
        options: GlobalOptions & {
          start: string;
          end?: string;
          calendar: string;
          description?: string;
          location?: string;
          attendees?: string;
        }
      ) => {
        try {
          const profileName = getActiveProfile(options.profile);
          const auth = await getAuthenticatedClient(profileName);
          const client = new CalendarClient(auth);

          const attendeesList = options.attendees
            ? options.attendees.split(',').map((email) => email.trim())
            : undefined;

          const eventId = await client.createEvent({
            calendarId: options.calendar,
            summary: title,
            start: options.start,
            end: options.end,
            description: options.description,
            location: options.location,
            attendees: attendeesList,
          });

          printSuccess(`Event created successfully! Event ID: ${eventId}`);
        } catch (error) {
          printError(
            'Error creating event: ' +
              (error instanceof Error ? error.message : String(error))
          );
          process.exit(1);
        }
      }
    );

  // calendar update
  calendar
    .command('update <event-id>')
    .description('Update an existing calendar event')
    .option('--title <text>', 'New event title')
    .option('--start <datetime>', 'New start date/time')
    .option('--end <datetime>', 'New end date/time')
    .option('--description <text>', 'New event description')
    .option('--location <place>', 'New event location')
    .option('--calendar <id>', 'Calendar ID', 'primary')
    .action(
      async (
        eventId: string,
        options: GlobalOptions & {
          title?: string;
          start?: string;
          end?: string;
          description?: string;
          location?: string;
          calendar: string;
        }
      ) => {
        try {
          const profileName = getActiveProfile(options.profile);
          const auth = await getAuthenticatedClient(profileName);
          const client = new CalendarClient(auth);

          await client.updateEvent(eventId, {
            calendarId: options.calendar,
            summary: options.title,
            start: options.start,
            end: options.end,
            description: options.description,
            location: options.location,
          });

          printSuccess('Event updated successfully!');
        } catch (error) {
          printError(
            'Error updating event: ' +
              (error instanceof Error ? error.message : String(error))
          );
          process.exit(1);
        }
      }
    );

  // calendar delete
  calendar
    .command('delete <event-id>')
    .description('Delete a calendar event')
    .option('--calendar <id>', 'Calendar ID', 'primary')
    .action(
      async (
        eventId: string,
        options: GlobalOptions & { calendar: string }
      ) => {
        try {
          const profileName = getActiveProfile(options.profile);
          const auth = await getAuthenticatedClient(profileName);
          const client = new CalendarClient(auth);

          await client.deleteEvent(eventId, options.calendar);

          printSuccess('Event deleted successfully!');
        } catch (error) {
          printError(
            'Error deleting event: ' +
              (error instanceof Error ? error.message : String(error))
          );
          process.exit(1);
        }
      }
    );
}

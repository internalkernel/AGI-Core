import Table from 'cli-table3';
import chalk from 'chalk';
import type {
  OutputFormat,
  EmailMessage,
  EmailDetail,
  Calendar,
  CalendarEvent,
  DriveFile,
} from '../types/index.js';

export interface FormatOptions {
  includeHeaders?: boolean;
  maxWidth?: number;
}

/**
 * Main formatter for CLI output
 */
export function formatOutput(
  data: any,
  format: OutputFormat,
  options?: FormatOptions
): string {
  switch (format) {
    case 'json':
      return JSON.stringify(data, null, 2);
    case 'table':
      // For table format, the data should be formatted by specific formatters
      // This is a fallback for simple objects
      if (Array.isArray(data)) {
        if (data.length === 0) return 'No data to display';
        const keys = Object.keys(data[0]);
        const table = new Table({
          head: keys.map((k) => chalk.cyan(k)),
        });
        data.forEach((item) => {
          table.push(keys.map((k) => String(item[k] ?? '')));
        });
        return table.toString();
      }
      return JSON.stringify(data, null, 2);
    case 'text':
      if (Array.isArray(data)) {
        return data.map((item) => JSON.stringify(item)).join('\n');
      }
      return String(data);
    default:
      return JSON.stringify(data, null, 2);
  }
}

/**
 * Format email list
 */
export function formatEmailList(
  emails: EmailMessage[],
  format: OutputFormat
): string {
  if (emails.length === 0) {
    return 'No emails found';
  }

  switch (format) {
    case 'json':
      return JSON.stringify(emails, null, 2);
    case 'table': {
      const table = new Table({
        head: [
          chalk.cyan('From'),
          chalk.cyan('Subject'),
          chalk.cyan('Date'),
          chalk.cyan('Unread'),
        ],
        colWidths: [30, 50, 20, 8],
        wordWrap: true,
      });
      emails.forEach((email) => {
        const unreadMark = email.isUnread ? chalk.yellow('●') : ' ';
        table.push([
          email.from,
          email.subject,
          formatDate(email.date),
          unreadMark,
        ]);
      });
      return table.toString();
    }
    case 'text':
      return emails
        .map((email) => {
          const unread = email.isUnread ? '[UNREAD] ' : '';
          return `${unread}${email.from} - ${email.subject} (${formatDate(email.date)})`;
        })
        .join('\n');
    default:
      return JSON.stringify(emails, null, 2);
  }
}

/**
 * Format email detail
 */
export function formatEmailDetail(
  email: EmailDetail,
  format: OutputFormat
): string {
  switch (format) {
    case 'json':
      return JSON.stringify(email, null, 2);
    case 'table':
    case 'text': {
      const lines: string[] = [];
      lines.push(chalk.bold('From: ') + email.from);
      lines.push(chalk.bold('To: ') + email.to);
      lines.push(chalk.bold('Subject: ') + email.subject);
      lines.push(chalk.bold('Date: ') + formatDate(email.date));
      lines.push(chalk.bold('Labels: ') + email.labels.join(', '));
      lines.push('');
      lines.push(chalk.bold('Body:'));
      lines.push(email.body);

      if (email.attachments.length > 0) {
        lines.push('');
        lines.push(chalk.bold('Attachments:'));
        email.attachments.forEach((att) => {
          lines.push(
            `  - ${att.filename} (${att.mimeType}, ${formatSize(att.size)})`
          );
        });
      }

      return lines.join('\n');
    }
    default:
      return JSON.stringify(email, null, 2);
  }
}

/**
 * Format calendar list
 */
export function formatCalendarList(
  calendars: Calendar[],
  format: OutputFormat
): string {
  if (calendars.length === 0) {
    return 'No calendars found';
  }

  switch (format) {
    case 'json':
      return JSON.stringify(calendars, null, 2);
    case 'table': {
      const table = new Table({
        head: [
          chalk.cyan('Summary'),
          chalk.cyan('ID'),
          chalk.cyan('Primary'),
          chalk.cyan('Access Role'),
        ],
        colWidths: [30, 40, 10, 15],
        wordWrap: true,
      });
      calendars.forEach((cal) => {
        table.push([
          cal.summary,
          cal.id,
          cal.primary ? chalk.green('Yes') : 'No',
          cal.accessRole,
        ]);
      });
      return table.toString();
    }
    case 'text':
      return calendars
        .map((cal) => {
          const primary = cal.primary ? '[PRIMARY] ' : '';
          return `${primary}${cal.summary} (${cal.id})`;
        })
        .join('\n');
    default:
      return JSON.stringify(calendars, null, 2);
  }
}

/**
 * Format event list
 */
export function formatEventList(
  events: CalendarEvent[],
  format: OutputFormat
): string {
  if (events.length === 0) {
    return 'No events found';
  }

  switch (format) {
    case 'json':
      return JSON.stringify(events, null, 2);
    case 'table': {
      const table = new Table({
        head: [
          chalk.cyan('Time'),
          chalk.cyan('Summary'),
          chalk.cyan('Location'),
          chalk.cyan('Calendar'),
        ],
        colWidths: [30, 40, 25, 25],
        wordWrap: true,
      });
      events.forEach((event) => {
        const timeRange = `${formatDate(event.start)} - ${formatDate(event.end)}`;
        table.push([
          timeRange,
          event.summary,
          event.location || '',
          event.calendarId,
        ]);
      });
      return table.toString();
    }
    case 'text':
      return events
        .map((event) => {
          const location = event.location ? ` @ ${event.location}` : '';
          return `${formatDate(event.start)} - ${event.summary}${location}`;
        })
        .join('\n');
    default:
      return JSON.stringify(events, null, 2);
  }
}

/**
 * Format Drive file list
 */
export function formatFileList(
  files: DriveFile[],
  format: OutputFormat
): string {
  if (files.length === 0) {
    return 'No files found';
  }

  switch (format) {
    case 'json':
      return JSON.stringify(files, null, 2);
    case 'table': {
      const table = new Table({
        head: [
          chalk.cyan('Name'),
          chalk.cyan('Type'),
          chalk.cyan('Size'),
          chalk.cyan('Modified'),
        ],
        colWidths: [40, 30, 15, 20],
        wordWrap: true,
      });
      files.forEach((file) => {
        table.push([
          file.name,
          getMimeTypeLabel(file.mimeType),
          file.size ? formatSize(parseInt(file.size)) : '-',
          formatDate(file.modifiedTime),
        ]);
      });
      return table.toString();
    }
    case 'text':
      return files
        .map((file) => {
          const size = file.size ? ` (${formatSize(parseInt(file.size))})` : '';
          return `${file.name}${size} - ${formatDate(file.modifiedTime)}`;
        })
        .join('\n');
    default:
      return JSON.stringify(files, null, 2);
  }
}

/**
 * Format profile list
 */
export function formatProfileList(
  profiles: { name: string; email?: string; isDefault: boolean }[],
  format: OutputFormat
): string {
  if (profiles.length === 0) {
    return 'No profiles found';
  }

  switch (format) {
    case 'json':
      return JSON.stringify(profiles, null, 2);
    case 'table': {
      const table = new Table({
        head: [chalk.cyan('Profile'), chalk.cyan('Email'), chalk.cyan('Default')],
        colWidths: [20, 40, 10],
        wordWrap: true,
      });
      profiles.forEach((profile) => {
        table.push([
          profile.name,
          profile.email || '-',
          profile.isDefault ? chalk.green('●') : '',
        ]);
      });
      return table.toString();
    }
    case 'text':
      return profiles
        .map((profile) => {
          const defaultMark = profile.isDefault ? ' (default)' : '';
          const email = profile.email ? ` - ${profile.email}` : '';
          return `${profile.name}${email}${defaultMark}`;
        })
        .join('\n');
    default:
      return JSON.stringify(profiles, null, 2);
  }
}

/**
 * Print message to stdout
 */
export function print(message: string): void {
  console.log(message);
}

/**
 * Print error message to stderr in red
 */
export function printError(message: string): void {
  console.error(chalk.red(message));
}

/**
 * Print success message in green
 */
export function printSuccess(message: string): void {
  console.log(chalk.green(message));
}

/**
 * Helper: Format date string
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  if (isNaN(date.getTime())) {
    return dateString;
  }

  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  // If today, show time
  if (days === 0) {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // If this year, show month and day
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  }

  // Otherwise show full date
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Helper: Format file size
 */
function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Helper: Get human-readable label for MIME type
 */
function getMimeTypeLabel(mimeType: string): string {
  const typeMap: Record<string, string> = {
    'application/vnd.google-apps.folder': 'Folder',
    'application/vnd.google-apps.document': 'Google Doc',
    'application/vnd.google-apps.spreadsheet': 'Google Sheet',
    'application/vnd.google-apps.presentation': 'Google Slides',
    'application/vnd.google-apps.form': 'Google Form',
    'application/pdf': 'PDF',
    'image/png': 'PNG Image',
    'image/jpeg': 'JPEG Image',
    'image/gif': 'GIF Image',
    'text/plain': 'Text File',
    'application/zip': 'ZIP Archive',
  };

  return typeMap[mimeType] || mimeType.split('/')[1]?.toUpperCase() || mimeType;
}

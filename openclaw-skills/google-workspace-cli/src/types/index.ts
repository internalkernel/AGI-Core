export interface GwcliConfig {
  defaultProfile?: string;
  version: string;
}

export interface ProfileConfig {
  email?: string;
  createdAt: string;
}

export interface OAuthCredentials {
  installed?: {
    client_id: string;
    client_secret: string;
    redirect_uris: string[];
  };
  web?: {
    client_id: string;
    client_secret: string;
    redirect_uris: string[];
  };
}

export interface TokenData {
  access_token: string;
  refresh_token: string;
  scope: string;
  token_type: string;
  expiry_date: number;
}

export interface ProfileCredentials {
  clientId: string;
  clientSecret: string;
  tokens: TokenData;
}

export type OutputFormat = 'json' | 'table' | 'text';

export interface GlobalOptions {
  profile?: string;
  format?: OutputFormat;
}

export interface EmailMessage {
  id: string;
  threadId: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  snippet: string;
  labels: string[];
  isUnread: boolean;
}

export interface EmailDetail extends EmailMessage {
  body: string;
  attachments: {
    filename: string;
    mimeType: string;
    size: number;
  }[];
}

export interface CalendarEvent {
  id: string;
  calendarId: string;
  summary: string;
  description?: string;
  start: string;
  end: string;
  location?: string;
  attendees?: string[];
  status: string;
}

export interface Calendar {
  id: string;
  summary: string;
  description?: string;
  primary: boolean;
  accessRole: string;
}

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  modifiedTime: string;
  parents?: string[];
  webViewLink?: string;
}

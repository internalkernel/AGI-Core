import { google, gmail_v1 } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { EmailMessage, EmailDetail } from '../types/index.js';

export class GmailClient {
  private gmail: gmail_v1.Gmail;
  private userEmail?: string;

  constructor(auth: OAuth2Client) {
    this.gmail = google.gmail({ version: 'v1', auth });
  }

  /**
   * List messages with optional filtering
   */
  async list(options: {
    maxResults?: number;
    unread?: boolean;
    query?: string;
  } = {}): Promise<EmailMessage[]> {
    const { maxResults = 50, unread = false, query = '' } = options;

    let q = query;
    if (unread) {
      q = q ? `${q} is:unread` : 'is:unread';
    }

    const response = await this.gmail.users.messages.list({
      userId: 'me',
      maxResults,
      q: q || undefined,
    });

    const messages = response.data.messages || [];

    // Fetch full details for each message
    const detailedMessages = await Promise.all(
      messages.map(async (msg) => {
        if (!msg.id) throw new Error('Message missing ID');
        const fullMessage = await this.gmail.users.messages.get({
          userId: 'me',
          id: msg.id,
        });
        return this.parseMessage(fullMessage.data);
      })
    );

    return detailedMessages;
  }

  /**
   * Search messages using Gmail query syntax
   */
  async search(query: string, maxResults: number = 50): Promise<EmailMessage[]> {
    return this.list({ query, maxResults });
  }

  /**
   * Get full message details including body
   */
  async read(messageId: string): Promise<EmailDetail> {
    const response = await this.gmail.users.messages.get({
      userId: 'me',
      id: messageId,
      format: 'full',
    });

    return this.parseMessageDetail(response.data);
  }

  /**
   * Get all messages in a thread
   */
  async getThread(threadId: string): Promise<EmailDetail[]> {
    const response = await this.gmail.users.threads.get({
      userId: 'me',
      id: threadId,
      format: 'full',
    });

    const messages = response.data.messages || [];
    return messages.map((msg) => this.parseMessageDetail(msg));
  }

  /**
   * Archive a message (remove INBOX label)
   */
  async archive(messageId: string): Promise<void> {
    await this.gmail.users.messages.modify({
      userId: 'me',
      id: messageId,
      requestBody: {
        removeLabelIds: ['INBOX'],
      },
    });
  }

  /**
   * Move a message to trash
   */
  async trash(messageId: string): Promise<void> {
    await this.gmail.users.messages.trash({
      userId: 'me',
      id: messageId,
    });
  }

  /**
   * Create a draft message
   */
  async createDraft(
    to: string,
    subject: string,
    body: string
  ): Promise<string> {
    const mimeMessage = this.createMimeMessage(to, subject, body);

    const response = await this.gmail.users.drafts.create({
      userId: 'me',
      requestBody: {
        message: {
          raw: mimeMessage,
        },
      },
    });

    if (!response.data.id) {
      throw new Error('Draft creation failed: no ID returned');
    }

    return response.data.id;
  }

  /**
   * Send an existing draft
   */
  async sendDraft(draftId: string): Promise<void> {
    await this.gmail.users.drafts.send({
      userId: 'me',
      requestBody: {
        id: draftId,
      },
    });
  }

  /**
   * Compose and send a message immediately
   */
  async send(to: string, subject: string, body: string): Promise<string> {
    const mimeMessage = this.createMimeMessage(to, subject, body);

    const response = await this.gmail.users.messages.send({
      userId: 'me',
      requestBody: {
        raw: mimeMessage,
      },
    });

    if (!response.data.id) {
      throw new Error('Message send failed: no ID returned');
    }

    return response.data.id;
  }

  /**
   * Reply to a message
   */
  async reply(messageId: string, body: string): Promise<string> {
    // Get original message to extract headers
    const original = await this.gmail.users.messages.get({
      userId: 'me',
      id: messageId,
      format: 'metadata',
      metadataHeaders: ['Subject', 'From', 'To', 'Message-ID'],
    });

    const headers = original.data.payload?.headers || [];
    const getHeader = (name: string) =>
      headers.find((h) => h.name?.toLowerCase() === name.toLowerCase())?.value || '';

    const originalSubject = getHeader('Subject');
    const originalFrom = getHeader('From');
    const originalMessageId = getHeader('Message-ID');
    const threadId = original.data.threadId || '';

    // Extract email from "Name <email>" format
    const toEmail = originalFrom.match(/<(.+)>/)
      ? originalFrom.match(/<(.+)>/)![1]
      : originalFrom;

    const replySubject = originalSubject.startsWith('Re:')
      ? originalSubject
      : `Re: ${originalSubject}`;

    const mimeMessage = this.createMimeMessage(
      toEmail,
      replySubject,
      body,
      originalMessageId
    );

    const response = await this.gmail.users.messages.send({
      userId: 'me',
      requestBody: {
        raw: mimeMessage,
        threadId,
      },
    });

    if (!response.data.id) {
      throw new Error('Reply send failed: no ID returned');
    }

    return response.data.id;
  }

  /**
   * Parse Gmail API message to EmailMessage format
   */
  private parseMessage(message: gmail_v1.Schema$Message): EmailMessage {
    const headers = message.payload?.headers || [];
    const getHeader = (name: string) =>
      headers.find((h) => h.name?.toLowerCase() === name.toLowerCase())?.value || '';

    return {
      id: message.id || '',
      threadId: message.threadId || '',
      subject: getHeader('Subject'),
      from: getHeader('From'),
      to: getHeader('To'),
      date: getHeader('Date'),
      snippet: message.snippet || '',
      labels: message.labelIds || [],
      isUnread: message.labelIds?.includes('UNREAD') || false,
    };
  }

  /**
   * Parse Gmail API message to EmailDetail format with body and attachments
   */
  private parseMessageDetail(message: gmail_v1.Schema$Message): EmailDetail {
    const baseMessage = this.parseMessage(message);
    const body = this.extractBody(message);
    const attachments = this.extractAttachments(message);

    return {
      ...baseMessage,
      body,
      attachments,
    };
  }

  /**
   * Extract message body from payload
   */
  private extractBody(message: gmail_v1.Schema$Message): string {
    const payload = message.payload;
    if (!payload) return '';

    // Check if body is directly available
    if (payload.body?.data) {
      return this.decodeBase64(payload.body.data);
    }

    // Search in parts for text/plain or text/html
    if (payload.parts) {
      // Prefer text/plain
      const textPart = payload.parts.find((part) => part.mimeType === 'text/plain');
      if (textPart?.body?.data) {
        return this.decodeBase64(textPart.body.data);
      }

      // Fall back to text/html
      const htmlPart = payload.parts.find((part) => part.mimeType === 'text/html');
      if (htmlPart?.body?.data) {
        return this.decodeBase64(htmlPart.body.data);
      }

      // Search nested multipart
      for (const part of payload.parts) {
        if (part.mimeType?.startsWith('multipart/') && part.parts) {
          const nestedText = part.parts.find((p) => p.mimeType === 'text/plain');
          if (nestedText?.body?.data) {
            return this.decodeBase64(nestedText.body.data);
          }
          const nestedHtml = part.parts.find((p) => p.mimeType === 'text/html');
          if (nestedHtml?.body?.data) {
            return this.decodeBase64(nestedHtml.body.data);
          }
        }
      }
    }

    return '';
  }

  /**
   * Extract attachments from message
   */
  private extractAttachments(
    message: gmail_v1.Schema$Message
  ): EmailDetail['attachments'] {
    const attachments: EmailDetail['attachments'] = [];
    const payload = message.payload;

    if (!payload?.parts) return attachments;

    const extractFromParts = (parts: gmail_v1.Schema$MessagePart[]) => {
      for (const part of parts) {
        if (part.filename && part.body?.attachmentId) {
          attachments.push({
            filename: part.filename,
            mimeType: part.mimeType || 'application/octet-stream',
            size: part.body.size || 0,
          });
        }

        // Recursively check nested parts
        if (part.parts) {
          extractFromParts(part.parts);
        }
      }
    };

    extractFromParts(payload.parts);
    return attachments;
  }

  /**
   * Decode base64url encoded string
   */
  private decodeBase64(encoded: string): string {
    // Gmail uses base64url encoding (RFC 4648)
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    return Buffer.from(base64, 'base64').toString('utf-8');
  }

  /**
   * Encode to base64url format
   */
  private encodeBase64(text: string): string {
    return Buffer.from(text, 'utf-8')
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }

  /**
   * Create RFC 2822 compliant MIME message
   */
  /** Strip CR/LF from header values to prevent email header injection */
  private sanitizeHeader(value: string): string {
    return value.replace(/[\r\n]/g, '');
  }

  private createMimeMessage(
    to: string,
    subject: string,
    body: string,
    inReplyTo?: string
  ): string {
    const lines = [
      `To: ${this.sanitizeHeader(to)}`,
      `Subject: ${this.sanitizeHeader(subject)}`,
      'Content-Type: text/plain; charset=utf-8',
      'MIME-Version: 1.0',
    ];

    if (inReplyTo) {
      const sanitizedReplyTo = this.sanitizeHeader(inReplyTo);
      lines.push(`In-Reply-To: ${sanitizedReplyTo}`);
      lines.push(`References: ${sanitizedReplyTo}`);
    }

    lines.push('', body);

    const mimeMessage = lines.join('\r\n');
    return this.encodeBase64(mimeMessage);
  }
}

import { google, drive_v3 } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import type { DriveFile } from '../types/index.js';

export class DriveClient {
  private drive: drive_v3.Drive;

  constructor(auth: OAuth2Client) {
    this.drive = google.drive({ version: 'v3', auth });
  }

  /**
   * List files/folders from Google Drive
   */
  async list(options?: { folderId?: string; maxResults?: number }): Promise<DriveFile[]> {
    const query = options?.folderId
      ? `'${options.folderId}' in parents and trashed = false`
      : 'trashed = false';

    const response = await this.drive.files.list({
      q: query,
      pageSize: options?.maxResults || 100,
      fields: 'files(id, name, mimeType, size, modifiedTime, parents, webViewLink)',
      orderBy: 'modifiedTime desc',
    });

    return (response.data.files || []).map(file => this.parseFile(file));
  }

  /**
   * Search files with Drive query syntax
   * Examples:
   * - "name contains 'invoice'"
   * - "mimeType = 'application/pdf'"
   * - "modifiedTime > '2025-01-01T00:00:00'"
   */
  async search(query: string, maxResults?: number): Promise<DriveFile[]> {
    const fullQuery = `${query} and trashed = false`;

    const response = await this.drive.files.list({
      q: fullQuery,
      pageSize: maxResults || 100,
      fields: 'files(id, name, mimeType, size, modifiedTime, parents, webViewLink)',
      orderBy: 'modifiedTime desc',
    });

    return (response.data.files || []).map(file => this.parseFile(file));
  }

  /**
   * Get file metadata
   */
  async getFileMetadata(fileId: string): Promise<DriveFile> {
    const response = await this.drive.files.get({
      fileId,
      fields: 'id, name, mimeType, size, modifiedTime, parents, webViewLink',
    });

    return this.parseFile(response.data);
  }

  /**
   * Download a file to disk
   */
  async download(fileId: string, outputPath: string): Promise<void> {
    const response = await this.drive.files.get(
      { fileId, alt: 'media' },
      { responseType: 'stream' }
    );

    const dest = createWriteStream(outputPath);
    await pipeline(response.data as any, dest);
  }

  /**
   * Export Google Doc/Sheet/Slide to specified format
   */
  async export(fileId: string, format: string, outputPath: string): Promise<void> {
    const mimeType = this.getMimeType(format);

    const response = await this.drive.files.export(
      { fileId, mimeType },
      { responseType: 'stream' }
    );

    const dest = createWriteStream(outputPath);
    await pipeline(response.data as any, dest);
  }

  /**
   * Parse Drive API file response to DriveFile
   */
  parseFile(file: drive_v3.Schema$File): DriveFile {
    return {
      id: file.id || '',
      name: file.name || '',
      mimeType: file.mimeType || '',
      size: file.size ?? undefined,
      modifiedTime: file.modifiedTime || '',
      parents: file.parents ?? undefined,
      webViewLink: file.webViewLink ?? undefined,
    };
  }

  /**
   * Get MIME type for export format
   */
  getMimeType(format: string): string {
    const mimeTypes: Record<string, string> = {
      // Google Docs
      pdf: 'application/pdf',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      txt: 'text/plain',
      md: 'text/markdown',
      html: 'text/html',

      // Google Sheets
      xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      csv: 'text/csv',

      // Google Slides
      pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    };

    const mimeType = mimeTypes[format.toLowerCase()];
    if (!mimeType) {
      throw new Error(`Unsupported export format: ${format}`);
    }

    return mimeType;
  }
}

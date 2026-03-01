import { Command } from 'commander';
import { GmailClient } from '../lib/gmail-client.js';
import { getAuthenticatedClient } from '../lib/auth.js';
import { getActiveProfile } from '../lib/config.js';
import { formatEmailList, formatEmailDetail, print, printSuccess, printError } from '../lib/output.js';
import type { GlobalOptions } from '../types/index.js';

/**
 * Register all Gmail subcommands
 */
export function registerGmailCommands(program: Command): void {
  const gmail = program
    .command('gmail')
    .description('Gmail operations');

  // gmail list [--unread] [--limit N]
  gmail
    .command('list')
    .description('List recent emails')
    .option('--unread', 'Only show unread emails')
    .option('--limit <n>', 'Maximum number of emails to return', '50')
    .action(async (options: { unread?: boolean; limit: string }, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const maxResults = parseInt(options.limit, 10);
        if (isNaN(maxResults) || maxResults < 1) {
          throw new Error('Limit must be a positive number');
        }

        const emails = await client.list({
          maxResults,
          unread: options.unread || false,
        });

        const output = formatEmailList(emails, globalOpts?.format || 'table');
        print(output);
      } catch (error) {
        printError(`Error listing emails: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail search <query> [--limit N]
  gmail
    .command('search <query>')
    .description('Search emails with Gmail query syntax')
    .option('--limit <n>', 'Maximum number of results', '50')
    .action(async (query: string, options: { limit: string }, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const maxResults = parseInt(options.limit, 10);
        if (isNaN(maxResults) || maxResults < 1) {
          throw new Error('Limit must be a positive number');
        }

        const emails = await client.search(query, maxResults);

        const output = formatEmailList(emails, globalOpts?.format || 'table');
        print(output);
      } catch (error) {
        printError(`Error searching emails: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail read <message-id>
  gmail
    .command('read <message-id>')
    .description('Read a specific email')
    .action(async (messageId: string, options: unknown, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const email = await client.read(messageId);

        const output = formatEmailDetail(email, globalOpts?.format || 'text');
        print(output);
      } catch (error) {
        printError(`Error reading email: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail thread <thread-id>
  gmail
    .command('thread <thread-id>')
    .description('View all messages in a thread')
    .action(async (threadId: string, options: unknown, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const emails = await client.getThread(threadId);

        // Display each message in the thread
        emails.forEach((email, index) => {
          if (index > 0) {
            print('\n' + '─'.repeat(80) + '\n');
          }
          const output = formatEmailDetail(email, globalOpts?.format || 'text');
          print(output);
        });
      } catch (error) {
        printError(`Error reading thread: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail archive <message-id>
  gmail
    .command('archive <message-id>')
    .description('Archive an email (remove from inbox)')
    .action(async (messageId: string, options: unknown, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        await client.archive(messageId);

        printSuccess(`Email ${messageId} archived successfully`);
      } catch (error) {
        printError(`Error archiving email: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail trash <message-id>
  gmail
    .command('trash <message-id>')
    .description('Move an email to trash')
    .action(async (messageId: string, options: unknown, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        await client.trash(messageId);

        printSuccess(`Email ${messageId} moved to trash`);
      } catch (error) {
        printError(`Error trashing email: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail draft --to <email> --subject <subject> --body <body>
  gmail
    .command('draft')
    .description('Create a draft email')
    .requiredOption('--to <email>', 'Recipient email address')
    .requiredOption('--subject <subject>', 'Email subject')
    .requiredOption('--body <body>', 'Email body')
    .action(async (options: { to: string; subject: string; body: string }, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const draftId = await client.createDraft(
          options.to,
          options.subject,
          options.body
        );

        printSuccess(`Draft created successfully with ID: ${draftId}`);
      } catch (error) {
        printError(`Error creating draft: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail send [draft-id] [--to <email>] [--subject <subject>] [--body <body>]
  gmail
    .command('send [draft-id]')
    .description('Send a draft or compose and send a new email')
    .option('--to <email>', 'Recipient email address (for new email)')
    .option('--subject <subject>', 'Email subject (for new email)')
    .option('--body <body>', 'Email body (for new email)')
    .action(async (draftId: string | undefined, options: { to?: string; subject?: string; body?: string }, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        if (draftId) {
          // Send existing draft
          await client.sendDraft(draftId);
          printSuccess(`Draft ${draftId} sent successfully`);
        } else {
          // Compose and send new email
          if (!options.to || !options.subject || !options.body) {
            throw new Error('When composing a new email, --to, --subject, and --body are required');
          }

          const messageId = await client.send(
            options.to,
            options.subject,
            options.body
          );

          printSuccess(`Email sent successfully with ID: ${messageId}`);
        }
      } catch (error) {
        printError(`Error sending email: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });

  // gmail reply <message-id> --body <body>
  gmail
    .command('reply <message-id>')
    .description('Reply to a message')
    .requiredOption('--body <body>', 'Reply body text')
    .action(async (messageId: string, options: { body: string }, command: Command) => {
      try {
        const globalOpts = command.parent?.optsWithGlobals() as GlobalOptions;
        const profileName = getActiveProfile(globalOpts?.profile);
        const auth = await getAuthenticatedClient(profileName);
        const client = new GmailClient(auth);

        const replyId = await client.reply(messageId, options.body);

        printSuccess(`Reply sent successfully with ID: ${replyId}`);
      } catch (error) {
        printError(`Error sending reply: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
      }
    });
}

import { google } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { createServer, IncomingMessage, ServerResponse } from 'http';
import { URL } from 'url';
import open from 'open';
import type { TokenData, ProfileCredentials } from '../types/index.js';
import { getProfileCredentials, saveProfileCredentials } from './config.js';

const SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/gmail.modify',
  'https://www.googleapis.com/auth/gmail.send',
  'https://www.googleapis.com/auth/calendar.readonly',
  'https://www.googleapis.com/auth/calendar.events',
  'https://www.googleapis.com/auth/drive.readonly',
];

/**
 * Starts a local HTTP server on an ephemeral port to receive the OAuth callback.
 * The server is kept alive (no close/reopen gap) to prevent local port race attacks.
 * Returns the server, its port, and a promise that resolves with the auth code.
 */
function startCallbackServer(expectedState: string): Promise<{ server: ReturnType<typeof createServer>; port: number; codePromise: Promise<string> }> {
  return new Promise((outerResolve, outerReject) => {
    let resolveCode: (code: string) => void;
    let rejectCode: (err: Error) => void;
    const codePromise = new Promise<string>((res, rej) => {
      resolveCode = res;
      rejectCode = rej;
    });

    const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      try {
        if (!req.url) {
          res.writeHead(400);
          res.end('Bad Request');
          return;
        }

        const url = new URL(req.url, 'http://localhost');
        const code = url.searchParams.get('code');
        const returnedState = url.searchParams.get('state');
        const error = url.searchParams.get('error');

        if (error) {
          res.writeHead(200, { 'Content-Type': 'text/plain' });
          res.end('Authentication failed. You can close this window.');
          server.close();
          rejectCode(new Error('OAuth authentication failed'));
          return;
        }

        // Validate CSRF state parameter
        if (returnedState !== expectedState) {
          res.writeHead(400, { 'Content-Type': 'text/plain' });
          res.end('Invalid state parameter. Possible CSRF attack.');
          server.close();
          rejectCode(new Error('OAuth state mismatch — possible CSRF'));
          return;
        }

        if (code) {
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end(`
            <html>
              <body>
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
              </body>
            </html>
          `);
          server.close();
          resolveCode(code);
          return;
        }

        res.writeHead(404);
        res.end('Not Found');
      } catch (err) {
        res.writeHead(500);
        res.end('Internal Server Error');
        server.close();
        rejectCode(err as Error);
      }
    });

    server.on('error', outerReject);
    // Bind to loopback only on ephemeral port — no close/reopen gap
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address === 'string') {
        server.close();
        outerReject(new Error('Failed to get port'));
        return;
      }
      const port = address.port;

      // Auto-timeout after 5 minutes to prevent hanging servers
      const timeout = setTimeout(() => {
        server.close();
        rejectCode(new Error('OAuth callback timed out after 5 minutes'));
      }, 300000);
      server.on('close', () => clearTimeout(timeout));

      outerResolve({ server, port, codePromise });
    });
  });
}

/**
 * Initiates the full OAuth flow for a profile
 *
 * @param profileName - The name of the profile to authenticate
 * @param clientId - OAuth client ID
 * @param clientSecret - OAuth client secret
 * @returns The authenticated OAuth2 client
 */
export async function initiateOAuthFlow(
  profileName: string,
  clientId: string,
  clientSecret: string
): Promise<OAuth2Client> {
  // Generate CSRF-safe state parameter
  const { randomBytes } = await import('crypto');
  const state = randomBytes(32).toString('hex');

  // Start callback server first (keeps port bound — no race window)
  const { port, codePromise } = await startCallbackServer(state);
  const redirectUri = `http://127.0.0.1:${port}`;

  // Create OAuth2 client
  const oauth2Client = new google.auth.OAuth2(
    clientId,
    clientSecret,
    redirectUri
  );

  // Generate auth URL
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: SCOPES,
    prompt: 'consent', // Force consent to ensure we get a refresh token
    state,
  });

  console.log('Opening browser for authentication...');
  console.log('If the browser does not open, visit this URL:');
  console.log(authUrl);
  console.log();

  // Open browser
  await open(authUrl);

  // Wait for callback
  console.log('Waiting for authentication...');
  const code = await codePromise;

  // Exchange code for tokens
  const { tokens } = await oauth2Client.getToken(code);
  oauth2Client.setCredentials(tokens);

  // Validate required token fields before storing
  if (!tokens.access_token || !tokens.refresh_token) {
    throw new Error('OAuth token exchange did not return required tokens (access_token, refresh_token).');
  }

  const tokenData: TokenData = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    scope: tokens.scope || SCOPES.join(' '),
    token_type: tokens.token_type || 'Bearer',
    expiry_date: tokens.expiry_date || 0,
  };

  const credentials: ProfileCredentials = {
    clientId,
    clientSecret,
    tokens: tokenData,
  };

  saveProfileCredentials(profileName, credentials);

  console.log('Authentication successful!');
  return oauth2Client;
}

/**
 * Gets an authenticated OAuth2 client for a profile
 * Automatically refreshes tokens if they're expired
 *
 * @param profileName - The name of the profile
 * @returns An authenticated OAuth2 client
 * @throws Error if profile has no credentials
 */
export async function getAuthenticatedClient(profileName: string): Promise<OAuth2Client> {
  const credentials = getProfileCredentials(profileName);

  if (!credentials) {
    throw new Error(
      `No credentials found for profile "${profileName}". ` +
      `Run: gwcli auth login --profile ${profileName}`
    );
  }

  // Create OAuth2 client with stored credentials
  const oauth2Client = new google.auth.OAuth2(
    credentials.clientId,
    credentials.clientSecret,
    'http://localhost' // Redirect URI not needed for token refresh
  );

  oauth2Client.setCredentials({
    access_token: credentials.tokens.access_token,
    refresh_token: credentials.tokens.refresh_token,
    scope: credentials.tokens.scope,
    token_type: credentials.tokens.token_type,
    expiry_date: credentials.tokens.expiry_date,
  });

  // Set up automatic token refresh
  oauth2Client.on('tokens', (tokens) => {
    try {
      if (!tokens.access_token) return;
      const updatedCredentials: ProfileCredentials = {
        ...credentials,
        tokens: {
          access_token: tokens.access_token,
          refresh_token: tokens.refresh_token || credentials.tokens.refresh_token,
          scope: tokens.scope || credentials.tokens.scope,
          token_type: tokens.token_type || credentials.tokens.token_type,
          expiry_date: tokens.expiry_date || credentials.tokens.expiry_date,
        },
      };
      saveProfileCredentials(profileName, updatedCredentials);
    } catch (err) {
      console.error(`Failed to persist refreshed tokens for profile "${profileName}":`, err);
    }
  });

  // Check if token is expired and refresh if needed
  const now = Date.now();
  if (credentials.tokens.expiry_date && credentials.tokens.expiry_date < now) {
    try {
      await oauth2Client.getAccessToken();
    } catch (error) {
      throw new Error(
        `Failed to refresh access token for profile "${profileName}". ` +
        `You may need to re-authenticate: gwcli auth login --profile ${profileName}\n` +
        `Error: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  return oauth2Client;
}

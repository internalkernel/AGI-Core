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
 * Gets an available port by temporarily binding to port 0
 */
async function getAvailablePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, () => {
      const address = server.address();
      if (!address || typeof address === 'string') {
        server.close();
        reject(new Error('Failed to get port'));
        return;
      }
      const port = address.port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

/**
 * Starts a local HTTP server to receive the OAuth callback
 */
function createCallbackServer(port: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      try {
        if (!req.url) {
          res.writeHead(400);
          res.end('Bad Request');
          return;
        }

        const url = new URL(req.url, 'http://localhost');
        const code = url.searchParams.get('code');
        const error = url.searchParams.get('error');

        if (error) {
          res.writeHead(200, { 'Content-Type': 'text/html' });
          res.end(`
            <html>
              <body>
                <h1>Authentication Failed</h1>
                <p>Error: ${error}</p>
                <p>You can close this window.</p>
              </body>
            </html>
          `);
          server.close();
          reject(new Error(`OAuth error: ${error}`));
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
          resolve(code);
          return;
        }

        res.writeHead(404);
        res.end('Not Found');
      } catch (err) {
        res.writeHead(500);
        res.end('Internal Server Error');
        server.close();
        reject(err);
      }
    });

    server.on('error', reject);
    server.listen(port);
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
  // Get an available port for the callback
  const port = await getAvailablePort();
  const redirectUri = `http://localhost:${port}`;

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
  });

  console.log('Opening browser for authentication...');
  console.log('If the browser does not open, visit this URL:');
  console.log(authUrl);
  console.log();

  // Open browser
  await open(authUrl);

  // Start callback server and wait for code
  console.log('Waiting for authentication...');
  const code = await createCallbackServer(port);

  // Exchange code for tokens
  const { tokens } = await oauth2Client.getToken(code);
  oauth2Client.setCredentials(tokens);

  // Store the credentials
  const tokenData: TokenData = {
    access_token: tokens.access_token!,
    refresh_token: tokens.refresh_token!,
    scope: tokens.scope!,
    token_type: tokens.token_type!,
    expiry_date: tokens.expiry_date!,
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
    // Update stored tokens when they're refreshed
    const updatedCredentials: ProfileCredentials = {
      ...credentials,
      tokens: {
        access_token: tokens.access_token!,
        refresh_token: tokens.refresh_token || credentials.tokens.refresh_token,
        scope: tokens.scope || credentials.tokens.scope,
        token_type: tokens.token_type || credentials.tokens.token_type,
        expiry_date: tokens.expiry_date || credentials.tokens.expiry_date,
      },
    };
    saveProfileCredentials(profileName, updatedCredentials);
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

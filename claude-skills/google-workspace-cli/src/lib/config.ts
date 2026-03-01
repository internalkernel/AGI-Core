import { homedir } from 'os';
import { join } from 'path';
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, rmSync, chmodSync } from 'fs';
import type { GwcliConfig, ProfileConfig, ProfileCredentials, OAuthCredentials, TokenData } from '../types/index.js';

const CONFIG_DIR = join(homedir(), '.config', 'gwcli');
const PROFILES_DIR = join(CONFIG_DIR, 'profiles');
const CONFIG_FILE = join(CONFIG_DIR, 'config.json');

export function ensureConfigDir(): void {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  } else {
    chmodSync(CONFIG_DIR, 0o700);
  }
  if (!existsSync(PROFILES_DIR)) {
    mkdirSync(PROFILES_DIR, { recursive: true, mode: 0o700 });
  } else {
    chmodSync(PROFILES_DIR, 0o700);
  }
}

export function getConfig(): GwcliConfig {
  ensureConfigDir();
  if (!existsSync(CONFIG_FILE)) {
    const defaultConfig: GwcliConfig = { version: '1.0' };
    writeFileSync(CONFIG_FILE, JSON.stringify(defaultConfig, null, 2));
    return defaultConfig;
  }
  return JSON.parse(readFileSync(CONFIG_FILE, 'utf-8'));
}

export function saveConfig(config: GwcliConfig): void {
  ensureConfigDir();
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), { mode: 0o600 });
}

export function getProfileDir(profileName: string): string {
  // Strict allowlist: alphanumeric, hyphens, underscores only (1-64 chars)
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(profileName)) {
    throw new Error(`Invalid profile name: "${profileName}". Use only letters, numbers, hyphens, and underscores (1-64 chars).`);
  }
  return join(PROFILES_DIR, profileName);
}

export function profileExists(profileName: string): boolean {
  return existsSync(getProfileDir(profileName));
}

export function listProfiles(): string[] {
  ensureConfigDir();
  if (!existsSync(PROFILES_DIR)) {
    return [];
  }
  return readdirSync(PROFILES_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);
}

export function getProfileConfig(profileName: string): ProfileConfig | null {
  const configPath = join(getProfileDir(profileName), 'config.json');
  if (!existsSync(configPath)) {
    return null;
  }
  return JSON.parse(readFileSync(configPath, 'utf-8'));
}

export function saveProfileConfig(profileName: string, config: ProfileConfig): void {
  const profileDir = getProfileDir(profileName);
  if (!existsSync(profileDir)) {
    mkdirSync(profileDir, { recursive: true, mode: 0o700 });
  }
  writeFileSync(join(profileDir, 'config.json'), JSON.stringify(config, null, 2), { mode: 0o600 });
}

export function getProfileCredentials(profileName: string): ProfileCredentials | null {
  const credsPath = join(getProfileDir(profileName), 'credentials.json');
  if (!existsSync(credsPath)) {
    return null;
  }
  return JSON.parse(readFileSync(credsPath, 'utf-8'));
}

export function saveProfileCredentials(profileName: string, credentials: ProfileCredentials): void {
  const profileDir = getProfileDir(profileName);
  if (!existsSync(profileDir)) {
    mkdirSync(profileDir, { recursive: true, mode: 0o700 });
  }
  const credsPath = join(profileDir, 'credentials.json');
  writeFileSync(credsPath, JSON.stringify(credentials, null, 2), { mode: 0o600 });
}

export function deleteProfile(profileName: string): boolean {
  const profileDir = getProfileDir(profileName);
  if (!existsSync(profileDir)) {
    return false;
  }
  rmSync(profileDir, { recursive: true });

  // If this was the default profile, clear it
  const config = getConfig();
  if (config.defaultProfile === profileName) {
    config.defaultProfile = undefined;
    saveConfig(config);
  }
  return true;
}

export function setDefaultProfile(profileName: string): void {
  const config = getConfig();
  config.defaultProfile = profileName;
  saveConfig(config);
}

export function getDefaultProfile(): string | undefined {
  return getConfig().defaultProfile;
}

export function getActiveProfile(explicitProfile?: string): string {
  // Priority: explicit flag > env var > default config
  const profile = explicitProfile
    || process.env.GWCLI_PROFILE
    || getDefaultProfile();

  if (!profile) {
    throw new Error('No profile specified. Use --profile, set GWCLI_PROFILE, or run: gwcli profiles set-default <name>');
  }

  if (!profileExists(profile)) {
    throw new Error(`Profile "${profile}" does not exist. Run: gwcli profiles add ${profile} --client <path>`);
  }

  return profile;
}

export function parseOAuthClientFile(filePath: string): { clientId: string; clientSecret: string } {
  if (!existsSync(filePath)) {
    throw new Error(`OAuth client file not found: ${filePath}`);
  }

  const content: OAuthCredentials = JSON.parse(readFileSync(filePath, 'utf-8'));
  const creds = content.installed || content.web;

  if (!creds) {
    throw new Error('Invalid OAuth client file. Expected "installed" or "web" credentials.');
  }

  return {
    clientId: creds.client_id,
    clientSecret: creds.client_secret
  };
}

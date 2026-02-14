import { homedir } from 'os';
import { join } from 'path';
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, rmSync } from 'fs';
import type { GwcliConfig, ProfileConfig, ProfileCredentials, OAuthCredentials, TokenData } from '../types/index.js';

const CONFIG_DIR = join(homedir(), '.config', 'gwcli');
const PROFILES_DIR = join(CONFIG_DIR, 'profiles');
const CONFIG_FILE = join(CONFIG_DIR, 'config.json');

export function ensureConfigDir(): void {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
  if (!existsSync(PROFILES_DIR)) {
    mkdirSync(PROFILES_DIR, { recursive: true });
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
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export function getProfileDir(profileName: string): string {
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
    mkdirSync(profileDir, { recursive: true });
  }
  writeFileSync(join(profileDir, 'config.json'), JSON.stringify(config, null, 2));
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
    mkdirSync(profileDir, { recursive: true });
  }
  writeFileSync(join(profileDir, 'credentials.json'), JSON.stringify(credentials, null, 2));
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

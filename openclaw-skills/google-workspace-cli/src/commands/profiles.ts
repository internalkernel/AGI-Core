import { Command } from 'commander';
import {
  listProfiles,
  profileExists,
  deleteProfile,
  setDefaultProfile,
  getDefaultProfile,
  parseOAuthClientFile,
  saveProfileConfig,
  getProfileConfig
} from '../lib/config.js';
import { initiateOAuthFlow } from '../lib/auth.js';
import { formatOutput } from '../lib/output.js';
import type { ProfileConfig } from '../types/index.js';

/**
 * Register all profile management subcommands
 */
export function registerProfilesCommands(program: Command): void {
  const profiles = program
    .command('profiles')
    .description('Manage authentication profiles');

  // profiles list
  profiles
    .command('list')
    .description('List all profiles')
    .action(async () => {
      try {
        const allProfiles = listProfiles();
        const defaultProfile = getDefaultProfile();

        if (allProfiles.length === 0) {
          console.log('No profiles configured.');
          console.log('Add a profile with: gwcli profiles add <name> --client <path>');
          return;
        }

        const profileData = allProfiles.map(name => {
          const config = getProfileConfig(name);
          const isDefault = name === defaultProfile;

          return {
            name: name,
            email: config?.email || 'N/A',
            default: isDefault ? 'Yes' : '',
            created: config?.createdAt ? new Date(config.createdAt).toLocaleDateString() : 'N/A'
          };
        });

        const output = formatOutput(profileData, 'table');
        console.log(output);
      } catch (error) {
        console.error('Error listing profiles:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  // profiles add
  profiles
    .command('add <name>')
    .description('Add a new profile by running OAuth flow')
    .requiredOption('--client <path>', 'Path to OAuth client credentials JSON file')
    .action(async (name: string, options: { client: string }) => {
      try {
        // Validate profile name
        if (!name || name.trim().length === 0) {
          throw new Error('Profile name cannot be empty');
        }

        // Check if profile already exists
        if (profileExists(name)) {
          throw new Error(`Profile "${name}" already exists. Use a different name or remove the existing profile first.`);
        }

        // Parse OAuth client file
        console.log(`Reading OAuth client credentials from: ${options.client}`);
        const { clientId, clientSecret } = parseOAuthClientFile(options.client);

        // Initiate OAuth flow
        console.log(`\nInitiating OAuth flow for profile: ${name}`);
        console.log('A browser window will open for authentication...\n');

        await initiateOAuthFlow(name, clientId, clientSecret);

        // Save profile configuration
        const profileConfig: ProfileConfig = {
          createdAt: new Date().toISOString()
        };

        saveProfileConfig(name, profileConfig);

        console.log(`\n✓ Profile "${name}" added successfully!`);

        // If this is the first profile, set it as default
        const allProfiles = listProfiles();
        if (allProfiles.length === 1) {
          setDefaultProfile(name);
          console.log(`✓ Set "${name}" as the default profile`);
        } else {
          console.log(`\nTo set this as the default profile, run:`);
          console.log(`  gwcli profiles set-default ${name}`);
        }
      } catch (error) {
        console.error('Error adding profile:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  // profiles remove
  profiles
    .command('remove <name>')
    .description('Delete a profile')
    .action(async (name: string) => {
      try {
        if (!profileExists(name)) {
          throw new Error(`Profile "${name}" does not exist`);
        }

        const defaultProfile = getDefaultProfile();
        const wasDefault = defaultProfile === name;

        const success = deleteProfile(name);

        if (!success) {
          throw new Error(`Failed to delete profile "${name}"`);
        }

        console.log(`✓ Profile "${name}" removed successfully`);

        if (wasDefault) {
          const remainingProfiles = listProfiles();
          if (remainingProfiles.length > 0) {
            console.log(`\nNote: "${name}" was the default profile.`);
            console.log('Set a new default with:');
            console.log(`  gwcli profiles set-default ${remainingProfiles[0]}`);
          }
        }
      } catch (error) {
        console.error('Error removing profile:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });

  // profiles set-default
  profiles
    .command('set-default <name>')
    .description('Set the default profile')
    .action(async (name: string) => {
      try {
        if (!profileExists(name)) {
          throw new Error(`Profile "${name}" does not exist`);
        }

        setDefaultProfile(name);
        console.log(`✓ Default profile set to: ${name}`);
      } catch (error) {
        console.error('Error setting default profile:', error instanceof Error ? error.message : String(error));
        process.exit(1);
      }
    });
}

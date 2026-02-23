#!/usr/bin/env node
/**
 * Skill Verifier - Runs skill tests in isolated Docker containers
 * and generates TEE attestations using dstack
 */

const fs = require('fs');
const path = require('path');
const { execFile, execFileSync } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);
const crypto = require('crypto');

// Try to load dstack SDK (will fail gracefully if not in TEE)
let DstackClient = null;
try {
  DstackClient = require('@phala/dstack-sdk').DstackClient;
} catch (e) {
  console.log('⚠️  dstack SDK not available - using simulated attestations');
}

// Configuration
const DSTACK_SOCKET = process.env.DSTACK_SOCKET || '/var/run/dstack.sock';
const DSTACK_SIMULATOR = process.env.DSTACK_SIMULATOR || 'http://localhost:8090';
const DOCKER_HOST = process.env.DOCKER_HOST || 'unix:///var/run/docker.sock';

class SkillVerifier {
  constructor() {
    this.workDir = path.join(__dirname, 'work');
    if (!fs.existsSync(this.workDir)) {
      fs.mkdirSync(this.workDir, { recursive: true });
    }
  }

  /**
   * Verify a skill package
   * @param {string} skillPackagePath - Path to skill tarball or directory
   * @returns {Object} Verification result with attestation
   */
  async verify(skillPackagePath) {
    const startTime = Date.now();
    // Sanitize skillId to prevent path traversal (strip unsafe chars, reject empty)
    const rawSkillId = path.basename(skillPackagePath, path.extname(skillPackagePath));
    const skillId = rawSkillId.replace(/[^a-zA-Z0-9._-]/g, '_');
    if (!skillId || skillId === '.' || skillId === '..') {
      throw new Error(`Invalid skill package name: ${rawSkillId}`);
    }
    const extractDir = path.join(this.workDir, skillId);
    // Verify extractDir stays inside workDir
    const resolvedExtract = path.resolve(extractDir);
    const resolvedWork = path.resolve(this.workDir);
    if (!resolvedExtract.startsWith(resolvedWork + path.sep)) {
      throw new Error(`Extract directory escapes work directory: ${skillId}`);
    }

    console.log(`\n🔍 Verifying skill: ${skillId}`);

    try {
      // Step 1: Extract skill package
      console.log('📦 Extracting skill package...');
      await this.extractSkill(skillPackagePath, extractDir);

      // Step 2: Load and validate manifest
      console.log('📋 Loading manifest...');
      const manifest = this.loadManifest(extractDir);

      // Step 3: Run tests in Docker
      console.log('🧪 Running tests in isolated container...');
      const testResult = await this.runTests(extractDir, manifest);

      // Step 4: Generate attestation
      console.log('🔐 Generating TEE attestation...');
      const attestation = await this.generateAttestation(skillId, testResult);

      // Step 5: Create final result
      const result = {
        skillId: `${manifest.name}@${manifest.version}`,
        timestamp: new Date().toISOString(),
        duration: Date.now() - startTime,
        result: testResult,
        attestation: attestation,
        manifest: {
          name: manifest.name,
          version: manifest.version,
          description: manifest.description
        }
      };

      console.log(`\n✅ Verification complete! Passed: ${testResult.passed}`);
      return result;

    } catch (error) {
      console.error(`\n❌ Verification failed: ${error.message}`);
      throw error;
    } finally {
      // Cleanup
      if (fs.existsSync(extractDir)) {
        fs.rmSync(extractDir, { recursive: true, force: true });
      }
    }
  }

  /**
   * Extract skill package to directory
   */
  async extractSkill(packagePath, targetDir) {
    if (fs.statSync(packagePath).isDirectory()) {
      fs.cpSync(packagePath, targetDir, { recursive: true });
    } else {
      fs.mkdirSync(targetDir, { recursive: true });
      // Validate tarball entries: reject symlinks/hardlinks, path traversal, and tar bombs
      const MAX_ENTRIES = 10000;
      const MAX_TOTAL_SIZE = 500 * 1024 * 1024; // 500MB max expanded size
      const { stdout: verboseListing } = await execFileAsync('tar', ['-tvzf', packagePath], { encoding: 'utf8', timeout: 30000 });
      const resolvedTarget = path.resolve(targetDir);
      const lines = verboseListing.split('\n').filter(Boolean);
      if (lines.length > MAX_ENTRIES) {
        throw new Error(`Archive contains ${lines.length} entries (max ${MAX_ENTRIES}). Possible tar bomb.`);
      }
      let totalSize = 0;
      for (const line of lines) {
        // tar -tv format: "lrwxrwxrwx ..." for symlinks, "hrwxr-xr-x ... link to ..." for hardlinks
        if (line.startsWith('l') || line.includes(' link to ')) {
          throw new Error(`Archive contains symlink/hardlink entry (rejected for security): ${line.trim()}`);
        }
        // Extract the filename and size from tar -tv output
        // Format: "perms user/group size date time filename..."
        // Use match to handle filenames with spaces correctly
        const match = line.match(/^\S+\s+\S+\s+(\d+)\s+\S+\s+\S+\s+(.*)/);
        if (!match) continue;
        const entrySize = parseInt(match[1], 10);
        const entry = match[2];
        if (!isNaN(entrySize)) {
          totalSize += entrySize;
          if (totalSize > MAX_TOTAL_SIZE) {
            throw new Error(`Archive expanded size exceeds ${MAX_TOTAL_SIZE} bytes. Possible tar bomb.`);
          }
        }
        // Reject absolute paths and parent-directory references
        if (entry && (entry.startsWith('/') || entry.split('/').includes('..'))) {
          throw new Error(`Archive entry contains absolute or traversal path: ${entry}`);
        }
        if (entry) {
          const resolved = path.resolve(targetDir, entry);
          if (!resolved.startsWith(resolvedTarget + path.sep) && resolved !== resolvedTarget) {
            throw new Error(`Archive entry escapes target directory: ${entry}`);
          }
        }
      }
      await execFileAsync('tar', ['-xzf', packagePath, '--no-same-owner', '--no-same-permissions', '-C', targetDir], { timeout: 60000 });

      // Post-extraction: reject symlinks that target outside the extraction directory
      const walkForSymlinks = (dir) => {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isSymbolicLink()) {
            const linkTarget = path.resolve(path.dirname(fullPath), fs.readlinkSync(fullPath));
            if (!linkTarget.startsWith(resolvedTarget + path.sep) && linkTarget !== resolvedTarget) {
              throw new Error(`Symlink escapes target directory: ${entry.name}`);
            }
          } else if (entry.isDirectory()) {
            walkForSymlinks(fullPath);
          }
        }
      };
      walkForSymlinks(targetDir);
    }
  }

  /**
   * Load and validate skill manifest
   */
  loadManifest(skillDir) {
    const manifestPath = path.join(skillDir, 'SKILL.md');
    if (!fs.existsSync(manifestPath)) {
      throw new Error('No SKILL.md found in package');
    }

    const content = fs.readFileSync(manifestPath, 'utf8');
    
    // Parse frontmatter
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    if (!match) {
      throw new Error('Invalid SKILL.md: no frontmatter found');
    }

    const manifest = {};
    match[1].split('\n').forEach(line => {
      const [key, ...valueParts] = line.split(':');
      if (key && valueParts.length > 0) {
        manifest[key.trim()] = valueParts.join(':').trim();
      }
    });

    // Validate required fields
    if (!manifest.name || !manifest.version) {
      throw new Error('Manifest missing required fields: name, version');
    }

    return manifest;
  }

  /**
   * Run skill tests in Docker container
   */
  async runTests(skillDir, manifest) {
    const containerName = `skill-test-${Date.now()}`;
    
    try {
      // Build test Dockerfile
      const dockerfile = this.generateDockerfile(manifest);
      fs.writeFileSync(path.join(skillDir, 'Dockerfile.test'), dockerfile);

      // Build image (--network none prevents fetching during build)
      console.log('   Building test container...');
      await execFileAsync('docker', ['build', '--network', 'none', '-f', path.join(skillDir, 'Dockerfile.test'), '-t', containerName, skillDir], {
        env: { ...process.env, DOCKER_HOST },
        timeout: 60000, // 60s build timeout
      });

      // Run tests
      console.log('   Running tests...');
      const startTime = Date.now();

      let stdout = '';
      let stderr = '';
      let exitCode = 0;

      try {
        const result = await execFileAsync('docker', [
          'run', '--rm',
          '--network', 'none',           // No outbound network access
          '--read-only',                  // Read-only root filesystem
          '--cap-drop', 'ALL',           // Drop all capabilities
          '--security-opt', 'no-new-privileges',
          '--pids-limit', '256',         // Limit process count
          '--memory', '512m',            // Memory limit
          '--cpus', '1',                 // CPU limit
          '--tmpfs', '/tmp:size=64m',    // Writable tmpfs for temp files
          containerName
        ], {
          env: { ...process.env, DOCKER_HOST },
          encoding: 'utf8',
          timeout: 30000 // 30s timeout
        });
        stdout = result.stdout;
      } catch (error) {
        exitCode = typeof error.code === 'number' ? error.code : 1;
        stdout = error.stdout || '';
        stderr = error.stderr || error.message;
      }

      const duration = Date.now() - startTime;

      return {
        passed: exitCode === 0,
        exitCode,
        stdout,
        stderr,
        duration
      };

    } finally {
      // Cleanup image
      try {
        await execFileAsync('docker', ['rmi', containerName], {
          env: { ...process.env, DOCKER_HOST },
        });
      } catch (e) {
        // Ignore cleanup errors
      }
    }
  }

  /**
   * Allowlisted base images for skill testing
   */
  static ALLOWED_IMAGES = new Set([
    'alpine:latest', 'alpine:3.19', 'alpine:3.20',
    'node:20-alpine', 'node:22-alpine', 'node:20-slim', 'node:22-slim',
    'python:3.11-alpine', 'python:3.12-alpine', 'python:3.11-slim', 'python:3.12-slim',
    'rust:1-alpine', 'rust:1-slim',
    'golang:1.22-alpine', 'golang:1.23-alpine',
    'ubuntu:22.04', 'ubuntu:24.04',
    'debian:bookworm-slim', 'debian:bullseye-slim',
  ]);

  /**
   * Validate a shell command string for Dockerfile use.
   * Only allows simple commands (alphanumeric, spaces, hyphens, dots, slashes, equals, commas, colons).
   * Rejects all shell metacharacters and dangerous programs.
   */
  validateShellCommand(cmd) {
    if (!cmd || typeof cmd !== 'string') return '';
    // Only allow safe characters: no shell operators, no subshells, no redirects
    if (/[^a-zA-Z0-9\s\-_.\/=,:"'\[\]]/.test(cmd)) {
      throw new Error(`Manifest command contains disallowed characters: ${cmd.slice(0, 80)}`);
    }
    // Reject shell control operators even as words
    if (/(\|\||&&|[;&|`$(){}<>!#~])/.test(cmd)) {
      throw new Error(`Manifest command contains shell operator: ${cmd.slice(0, 80)}`);
    }
    // Reject dangerous commands
    const dangerous = /\b(curl|wget|nc|ncat|socat|ssh|scp|rsync|apt-key|gpg\s+--recv|chmod\s+[0-7]*s|chown|mount|umount|dd\s+if=|mkfs|fdisk|kill|pkill|reboot|shutdown|su\b|sudo)\b/i;
    if (dangerous.test(cmd)) {
      throw new Error(`Manifest command contains disallowed program: ${cmd.match(dangerous)[0]}`);
    }
    return cmd;
  }

  /**
   * Generate Dockerfile for testing
   */
  generateDockerfile(manifest) {
    // Validate base image against allowlist
    const baseImage = manifest.runtime || 'alpine:latest';
    if (!SkillVerifier.ALLOWED_IMAGES.has(baseImage)) {
      throw new Error(
        `Disallowed runtime image "${baseImage}". ` +
        `Allowed: ${[...SkillVerifier.ALLOWED_IMAGES].join(', ')}`
      );
    }

    // Validate shell commands
    const testDeps = this.validateShellCommand(manifest.test_deps);
    const testCommand = this.validateShellCommand(manifest.test_command);

    return `FROM ${baseImage}

WORKDIR /skill

# Copy skill files
COPY . .

# Install test dependencies if specified
${testDeps ? `RUN ["sh", "-c", ${JSON.stringify(testDeps)}]` : ''}

# Run tests
${testCommand ? `CMD ["sh", "-c", ${JSON.stringify(testCommand)}]` : 'CMD ["sh", "-c", "echo \\"No test command specified\\""]'}
`;
  }

  /**
   * Generate TEE attestation using dstack
   */
  async generateAttestation(skillId, testResult) {
    // Create result hash
    const resultJson = JSON.stringify({
      skillId,
      passed: testResult.passed,
      exitCode: testResult.exitCode,
      duration: testResult.duration
    });
    
    const resultHash = crypto.createHash('sha256').update(resultJson).digest();
    const reportData = resultHash.toString('hex');

    // Try real dstack SDK first (production TEE)
    if (DstackClient) {
      try {
        // Try production socket first
        let client;
        if (fs.existsSync(DSTACK_SOCKET)) {
          client = new DstackClient();
          console.log('🔐 Using production dstack socket');
        } else {
          // Fall back to simulator
          client = new DstackClient(DSTACK_SIMULATOR);
          console.log('🧪 Using dstack simulator');
        }
        
        const quoteResponse = await client.getQuote(reportData);
        
        return {
          quote: quoteResponse.quote,
          eventLog: quoteResponse.event_log,
          resultHash: reportData,
          verifier: 'dstack-sdk',
          teeType: 'intel-tdx'
        };
      } catch (error) {
        console.log(`⚠️  dstack SDK error: ${error.message}`);
      }
    }

    // Fallback: no real TEE available
    return {
      quote: null,
      resultHash: reportData,
      verifier: 'none',
      note: 'No TEE available - deploy to dstack for real attestations'
    };
  }

  /**
   * Get quote from dstack simulator
   */
  async getQuote(data) {
    // This would use the dstack SDK
    // For now, return mock data
    return {
      quote: '0x' + crypto.randomBytes(64).toString('hex'),
      eventLog: []
    };
  }
}

// CLI usage
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log('Usage: verifier.js <skill-package>');
    process.exit(1);
  }

  const verifier = new SkillVerifier();
  
  verifier.verify(args[0])
    .then(result => {
      console.log('\n📊 Results:');
      console.log(JSON.stringify(result, null, 2));
      
      // Save result (sanitize skillId to prevent path traversal)
      const safeSkillId = result.skillId.replace(/[^a-zA-Z0-9._-]/g, '_');
      const outputPath = path.join(__dirname, 'work', `${safeSkillId}.json`);
      const resolvedOutput = path.resolve(outputPath);
      const resolvedWork = path.resolve(path.join(__dirname, 'work'));
      if (!resolvedOutput.startsWith(resolvedWork + path.sep)) {
        throw new Error('Output path escapes work directory');
      }
      fs.writeFileSync(resolvedOutput, JSON.stringify(result, null, 2));
      console.log(`\n💾 Saved to: ${outputPath}`);
      
      process.exit(result.result.passed ? 0 : 1);
    })
    .catch(error => {
      console.error('Fatal error:', error);
      process.exit(1);
    });
}

module.exports = SkillVerifier;

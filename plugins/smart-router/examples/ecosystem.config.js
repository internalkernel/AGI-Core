// PM2 ecosystem configuration for smart-router + OpenClaw multi-agent setup.
//
// Usage:
//   pm2 start ecosystem.config.js
//   pm2 restart all --update-env
//
// Prerequisites:
//   - Set ANTHROPIC_API_KEY, SYNTHETIC_API_KEY, GOOGLE_API_KEY in your shell env
//   - Install smart-router deps: cd ~/.openclaw/smart-router-server && npm install
//   - Configure each agent profile (see examples/auth-profiles.json, models.json)

module.exports = {
  apps: [
    // ── Smart Router (must start first) ─────────────────────────────────
    {
      name: 'smart-router',
      script: 'server.js',
      cwd: `${process.env.HOME}/.openclaw/smart-router-server`,
      interpreter: 'node',
      env: {
        ROUTER_PORT: '9999',
        // IMPORTANT: Set ROUTER_API_KEY to a strong random secret in production.
        // All non-health endpoints require Bearer auth when this is set.
        // Without it, auth is BLOCKED unless ROUTER_ALLOW_UNAUTHENTICATED=true.
        ROUTER_API_KEY: process.env.ROUTER_API_KEY || '',
        // Set to 'true' ONLY for local development without auth:
        // ROUTER_ALLOW_UNAUTHENTICATED: 'true',
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
        SYNTHETIC_API_KEY: process.env.SYNTHETIC_API_KEY,
        GOOGLE_API_KEY: process.env.GOOGLE_API_KEY,
        OLLAMA_URL: 'http://localhost:11434'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '512M'
    },

    // ── OpenClaw Agents ─────────────────────────────────────────────────
    // Each agent runs as a separate OpenClaw gateway with its own profile
    // and workspace. Customize the agent names, ports, and tokens below.
    {
      name: 'openclaw-content-specialist',
      script: 'openclaw',
      args: '--profile content-specialist gateway --allow-unconfigured --port 8410 --force',
      cwd: process.env.HOME,
      env: {
        OPENCLAW_WORKSPACE: `${process.env.HOME}/.openclaw/workspaces/agent-content-specialist`,
        OPENCLAW_AGENT_ID: 'content-specialist',
        OPENCLAW_AGENT_NAME: 'Content Specialist Agent',
        OPENCLAW_PORT: '8410',
        // WARNING: Replace with a strong random token in production
        OPENCLAW_GATEWAY_TOKEN: process.env.OPENCLAW_GATEWAY_TOKEN || 'CHANGE_ME',
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
        GOOGLE_API_KEY: process.env.GOOGLE_API_KEY,
        SYNTHETIC_API_KEY: process.env.SYNTHETIC_API_KEY,
        OLLAMA_URL: 'http://localhost:11434',
        SMART_ROUTER_API_KEY: 'local-plugin-no-key-needed'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '2G'
    },
    {
      name: 'openclaw-devops',
      script: 'openclaw',
      args: '--profile devops gateway --allow-unconfigured --port 8420 --force',
      cwd: process.env.HOME,
      env: {
        OPENCLAW_WORKSPACE: `${process.env.HOME}/.openclaw/workspaces/agent-devops`,
        OPENCLAW_AGENT_ID: 'devops',
        OPENCLAW_AGENT_NAME: 'DevOps Agent',
        OPENCLAW_PORT: '8420',
        // WARNING: Replace with a strong random token in production
        OPENCLAW_GATEWAY_TOKEN: process.env.OPENCLAW_GATEWAY_TOKEN || 'CHANGE_ME',
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
        GOOGLE_API_KEY: process.env.GOOGLE_API_KEY,
        SYNTHETIC_API_KEY: process.env.SYNTHETIC_API_KEY,
        OLLAMA_URL: 'http://localhost:11434',
        SMART_ROUTER_API_KEY: 'local-plugin-no-key-needed'
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '2G'
    },
  ]
};

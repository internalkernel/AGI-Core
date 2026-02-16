# OpenClaw Dashboard

> **Fork Notice:** This project is a fork of the original [OpenClaw Dashboard](https://github.com/LvcidPsyche/openclaw-dashboard) created by [LvcidPsyche](https://github.com/LvcidPsyche). Full credit to the original maintainers for the foundation — monitoring UI, discovery engine, job management, and the FastAPI + React architecture this build extends. This fork adds multi-agent workspace support, authentication, real-time activity feeds, a calendar, project file browsing, and other features listed below.

A free, open-source monitoring and management dashboard for [OpenClaw](https://openclaw.ai) AI agent workflows.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg)
![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6.svg)

## What It Does

### Updated Areas

New pages and capabilities added in this fork:

- **Multi-Agent Setup** — Four specialized agent workspaces (Content Specialist, DevOps, Support Coordinator, Wealth Strategist) with per-agent identity, configuration, and project directories
- **Authentication** — JWT-based login with admin credentials, auth middleware on all API routes
- **Activity Feed** — Real-time WebSocket activity stream with event types, timestamps, and agent attribution
- **Calendar** — Event scheduling and calendar views for managing agent tasks and deadlines
- **Channels** — Communication channel configuration with per-channel agent assignments and enable/disable toggles
- **Projects** — File browser replacing Pipelines — browse agent project outputs with expandable folder trees and inline markdown preview
- **Global Search** — Keyboard-shortcut-accessible search across agents, skills, and content
- **Database & Redis** — PostgreSQL persistence and Redis caching layer for session and activity data
- **Webhooks** — Inbound webhook endpoint for external activity ingestion

### Original Functionality

Core features from the [original dashboard](https://github.com/LvcidPsyche/openclaw-dashboard):

- **Overview** — Real-time stats: active jobs, token usage, costs, system health
- **Jobs** — Full CRUD: create, edit, delete, run now, view run history for cron jobs
- ~~**Pipelines** — Auto-discovered pipelines with status and stage visualization~~ *(replaced by Projects)*
- **Agents** — Detected agents with type classification and capabilities
- **Skills** — Browse installed skills with categories, search, and README viewer
- **Config** — Tabbed configuration editor (General, Models, Gateway, Agents, Skills, Raw JSON)
- **Nodes** — Connected nodes and paired device management (approve/reject/revoke/rotate tokens)
- **Metrics** — Token usage charts, cost breakdown by model, daily trends, CSV export
- **System** — CPU, memory, and disk gauges with health checks
- **Logs** — Real-time log viewer with search, auto-scroll, and download
- **Debug** — Gateway diagnostics, health checks, filesystem status, session inspector, log tail
- **Docs** — Curated OpenClaw documentation links and quick reference
- **Chat** — AI chat proxy with model selector and extended thinking toggle
- **Sessions** — Session management with usage stats, history, model/thinking settings
- ~~**Settings** — Discovery engine, keyboard shortcuts reference, system info~~ *(merged into Config)*

## Screenshots

| Activity Feed | Calendar |
|---------------|----------|
| ![Activity Feed](docs/screenshots/dashboard-activity.png) | ![Calendar](docs/screenshots/dashboard-calendar.png) |

| Projects | Channels |
|----------|----------|
| ![Projects](docs/screenshots/dashboard-projects.png) | ![Channels](docs/screenshots/dashboard-channels.png) |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ and Redis 7+
- An OpenClaw installation (the dashboard reads from `~/.openclaw/`)

### 1. Clone and install

```bash
git clone https://github.com/LvcidPsyche/openclaw-dashboard.git
cd openclaw-dashboard

# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure (optional)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your paths
```

The defaults work if OpenClaw is installed at `~/.openclaw/`.

### 3. Run

**Development** (hot reload on both ends):

```bash
# Terminal 1 — Backend
cd backend
PYTHONPATH=. python -m app.main

# Terminal 2 — Frontend dev server
cd frontend
npm run dev
```

**Production** (single process, single port):

```bash
# Build the frontend
cd frontend && npm run build && cd ..

# Run everything on port 8765
cd backend
PYTHONPATH=. python -m app.main
```

The backend serves the built frontend automatically — no separate web server needed.

## Features

### Multi-Agent Workspaces
Four specialized agents, each with their own workspace, identity, skills access, and project output directories. Switch between agents across the dashboard to view per-agent data.

### Activity Feed & Calendar
Real-time WebSocket activity stream tracking agent events, task completions, and system changes. Calendar page for scheduling and viewing agent tasks with day/week/month views.

### Project File Browser
Browse agent project outputs organized into named folders. Expandable file trees with inline markdown preview — click any `.md` file to render it in a side panel with formatted headings, bold, italic, code blocks, lists, and links.

### Authentication & Security
JWT-based login, auth middleware protecting all API routes, security headers (CSP, X-Frame-Options, X-Content-Type-Options), CORS restrictions, request size limiting, and secret redaction in config responses.

### Full Job Management
Create, edit, delete, and run cron jobs directly from the dashboard. Supports cron expressions with preset helpers and interval-based scheduling.

### Configuration Editor
Tabbed editor for OpenClaw configuration with sections for general settings, models, gateway, agents, skills, and raw JSON editing. Secrets are automatically redacted in API responses.

### Node & Device Management
View connected nodes, manage paired devices with approve/reject/revoke/rotate token actions.

### Session Management
View all chat sessions with usage stats, switch models, toggle extended thinking, and review chat history.

### Debug & Diagnostics
Gateway connection testing, health checks, filesystem status verification, active session inspector, and live log tail.

### Customer-Quality UX
- Toast notifications on all mutations
- Keyboard shortcuts (`g+o` Overview, `g+j` Jobs, `/` focus search, `Esc` close modals)
- CSV export on Jobs, Metrics pages
- Log file download
- Confirmation dialogs for destructive actions
- Loading skeletons and empty states on every page

## Project Structure

```
backend/
  app/
    main.py              # FastAPI entry point + middleware + auth
    config.py            # Environment-based settings (Pydantic)
    routers/             # API modules
      overview.py        #   GET  /api/overview
      auth.py            #   POST /api/auth/login
      jobs.py            #   CRUD /api/jobs + run/history
      metrics.py         #   GET  /api/metrics/*
      system.py          #   GET  /api/system/*
      sessions.py        #   GET  /api/sessions
      sessions_mgmt.py   #   CRUD /api/sessions/*
      chat.py            #   POST /api/chat, WS /ws/chat
      logs.py            #   GET  /api/logs/*
      discovery.py       #   GET  /api/discovery, agents, skills
      config.py          #   GET/PUT /api/config
      nodes.py           #   GET /api/nodes + device actions
      debug.py           #   GET /api/debug/*
      activity.py        #   GET /api/activity
      calendar.py        #   CRUD /api/calendar
      channels.py        #   CRUD /api/channels
      projects.py        #   GET /api/projects + tree + file
      search.py          #   GET /api/search
      webhook.py         #   POST /api/webhook/activity
    services/
      gateway_rpc.py     # Shared gateway WebSocket RPC client
      job_service.py     # Cron job data + control
      cache_trace.py     # Token/cost analytics
      auth.py            # JWT auth + admin seeding
      calendar.py        # Calendar event service
      event_bus.py       # Real-time event broadcasting
    middleware/
      security.py        # Security headers + request size limiting
    discovery/
      engine.py          # Auto-discovery engine
      patterns.py        # Pipeline/agent/skill detection
    db/
      connection.py      # PostgreSQL async connection
    redis/
      client.py          # Redis connection
    models/
      schemas.py         # Pydantic response models
      database.py        # SQLAlchemy models
    websocket/
      manager.py         # Multi-channel WebSocket manager
  requirements.txt
  .env.example

frontend/
  src/
    pages/               # 18 page components
    components/
      layout/            # Sidebar, Header, Layout
      common/            # StatCard, StatusBadge, EmptyState, LoadingState, Toast, ConfirmDialog
      features/          # JobFormModal, ActivityFeed, AuthGuard, CalendarWidget, GlobalSearch
    api/                 # Typed fetch client + endpoints
    store/               # Zustand global state
    hooks/               # usePolling, useToast, useKeyboardShortcuts, useAuth, useActivityStream, useGlobalSearch
    constants/           # Agent definitions
    utils/               # Formatters
```

## Discovery Engine

The dashboard includes an auto-discovery engine that scans your OpenClaw workspace and detects:

| What | How |
|------|-----|
| **Pipelines** | Matches directory names against known patterns and checks file modification times for active/idle status |
| **Agents** | Scans agent config directories for JSON files with agent definitions, classifies by type |
| **Skills** | Enumerates `workspace/skills/`, auto-categorizes by name, reads README.md for descriptions |
| **Modules** | Checks for known custom module directories |

Discovery runs automatically every 5 minutes. Trigger a manual re-scan from Settings or via `POST /api/discovery/refresh`.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate and get JWT token |
| `GET` | `/api/overview` | Dashboard summary stats |
| `GET` | `/api/jobs` | All cron jobs with status |
| `POST` | `/api/jobs` | Create a new cron job |
| `PUT` | `/api/jobs/{id}` | Update a cron job |
| `DELETE` | `/api/jobs/{id}` | Delete a cron job |
| `POST` | `/api/jobs/{id}/run` | Trigger immediate job run |
| `GET` | `/api/jobs/{id}/runs` | Job run history |
| `POST` | `/api/jobs/control` | Control a job (enable/disable) |
| `GET` | `/api/config` | Current config (secrets redacted) |
| `PUT` | `/api/config` | Update configuration |
| `POST` | `/api/config/apply` | Apply config changes |
| `GET` | `/api/config/schema` | Config schema |
| `GET` | `/api/models` | Available models list |
| `GET` | `/api/nodes` | Connected nodes |
| `GET` | `/api/nodes/devices` | Paired devices |
| `POST` | `/api/nodes/devices/{id}/approve` | Approve device pairing |
| `POST` | `/api/nodes/devices/{id}/reject` | Reject device pairing |
| `POST` | `/api/nodes/devices/{id}/revoke` | Revoke device token |
| `POST` | `/api/nodes/devices/{id}/rotate` | Rotate device token |
| `GET` | `/api/metrics/tokens` | Token usage by model |
| `GET` | `/api/metrics/timeseries` | Time-series usage data |
| `GET` | `/api/metrics/breakdown` | Cost/token breakdown |
| `GET` | `/api/system/resources` | CPU, memory, disk stats |
| `GET` | `/api/system/health` | Service health checks |
| `GET` | `/api/sessions` | Active sessions |
| `GET` | `/api/sessions/list` | All sessions with details |
| `PATCH` | `/api/sessions/{id}` | Update session settings |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `GET` | `/api/sessions/{id}/usage` | Session token usage |
| `GET` | `/api/sessions/{id}/history` | Session chat history |
| `GET` | `/api/sessions/usage/timeseries` | Usage over time |
| `GET` | `/api/activity` | Activity feed events |
| `GET` | `/api/calendar` | Calendar events |
| `POST` | `/api/calendar` | Create calendar event |
| `GET` | `/api/channels` | Communication channels |
| `PUT` | `/api/channels/{id}` | Update channel config |
| `GET` | `/api/projects?agent={id}` | List agent project folders |
| `GET` | `/api/projects/{agent}/{project}/tree` | Project file tree |
| `GET` | `/api/projects/{agent}/file?path=` | Read project file content |
| `GET` | `/api/search` | Global search |
| `POST` | `/api/webhook/activity` | Inbound activity webhook |
| `GET` | `/api/debug/health` | Detailed health check |
| `GET` | `/api/debug/status` | Full system status |
| `GET` | `/api/debug/presence` | System presence |
| `GET` | `/api/debug/gateway` | Gateway connection test |
| `GET` | `/api/debug/sessions` | Sessions with usage |
| `GET` | `/api/debug/logs` | Recent log tail |
| `GET` | `/api/debug/filesystem` | Filesystem checks |
| `GET` | `/api/pipelines` | Discovered pipelines |
| `GET` | `/api/agents` | Discovered agents |
| `GET` | `/api/skills` | Skills (search, filter, paginate) |
| `GET` | `/api/skills/categories` | Skill category counts |
| `GET` | `/api/skills/{name}` | Skill detail + README |
| `GET` | `/api/discovery` | Full discovery result |
| `POST` | `/api/discovery/refresh` | Trigger re-scan |
| `GET` | `/api/logs/files` | Available log files |
| `GET` | `/api/logs/tail` | Tail a log file |
| `POST` | `/api/chat` | Send message to gateway |
| `GET` | `/api/chat/status` | Gateway availability |
| `WS` | `/ws/chat` | WebSocket chat |
| `WS` | `/ws/realtime` | Real-time overview updates |
| `WS` | `/ws/activity` | Real-time activity stream |

Interactive API docs available at `/docs` when the server is running.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Uvicorn, Pydantic, httpx, psutil, SQLAlchemy, Redis |
| Frontend | React 19, TypeScript 5.9, Vite 7 |
| Styling | Tailwind CSS 4 |
| Charts | Recharts 3 |
| State | Zustand 5 |
| Icons | Lucide React |
| Routing | React Router 7 |
| Database | PostgreSQL (asyncpg) |
| Cache | Redis |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `g` then `o` | Go to Overview |
| `g` then `j` | Go to Jobs |
| `g` then `p` | Go to Projects |
| `g` then `a` | Go to Agents |
| `g` then `s` | Go to Skills |
| `g` then `m` | Go to Metrics |
| `g` then `l` | Go to Logs |
| `g` then `c` | Go to Chat |
| `/` | Focus search |
| `Esc` | Close modals |

## Environment Variables

All variables are prefixed with `OPENCLAW_DASH_`. See [`backend/.env.example`](backend/.env.example) for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_DIR` | `~/.openclaw` | OpenClaw installation path |
| `GATEWAY_URL` | `http://localhost:18789` | Gateway HTTP URL |
| `GATEWAY_WS_URL` | `ws://127.0.0.1:18789` | Gateway WebSocket URL |
| `PORT` | `8765` | Server port |
| `DATABASE_URL` | | PostgreSQL connection string |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection string |
| `SECRET_KEY` | | JWT signing key |
| `ADMIN_PASSWORD` | `changeme` | Admin login password |
| `DISCOVERY_INTERVAL_SECONDS` | `300` | Auto-discovery refresh interval |

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)

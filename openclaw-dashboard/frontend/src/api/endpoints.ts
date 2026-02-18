import { apiFetch, apiPost, apiPut, apiPatch, apiDelete } from './client';
import type {
  DashboardOverview, JobStatus, SystemResources, TokenMetricsResponse,
  TimeSeriesPoint, MetricsBreakdown, Pipeline, Agent, AgentDetail, SkillInfo,
  SkillCategory, DiscoveryResult, SessionInfo, DeviceInfo, LogFile,
  ConfigData, GatewayStatus, ChannelConfig, ProjectInfo, FileNode,
} from './types';

// Overview
export const fetchOverview = () => apiFetch<DashboardOverview>('/api/overview');

// Jobs
export const fetchJobs = () => apiFetch<JobStatus[]>('/api/jobs');
export const fetchJobHistory = (id: string) => apiFetch<{ history: any[] }>(`/api/jobs/${id}/history`);
export const controlJob = (job_id: string, action: string) =>
  apiPost<{ status: string }>('/api/jobs/control', { job_id, action });
export const createJob = (data: any) => apiPost<{ status: string; job: any }>('/api/jobs', data);
export const updateJob = (id: string, data: any) => apiPut<{ status: string }>(`/api/jobs/${id}`, data);
export const deleteJob = (id: string) => apiDelete<{ status: string }>(`/api/jobs/${id}`);
export const runJob = (id: string) => apiPost<{ status: string }>(`/api/jobs/${id}/run`, {});

// Metrics
export const fetchTokenMetrics = (days = 7) =>
  apiFetch<TokenMetricsResponse>(`/api/metrics/tokens?days=${days}`);
export const fetchTimeseries = (metric = 'tokens', hours = 24) =>
  apiFetch<{ data: TimeSeriesPoint[]; models: string[] }>(`/api/metrics/timeseries?metric=${metric}&hours=${hours}`);
export const fetchBreakdown = () => apiFetch<MetricsBreakdown>('/api/metrics/breakdown');
export const fetchAgentTimeseries = (metric = 'tokens', hours = 168) =>
  apiFetch<{ data: TimeSeriesPoint[]; agents: string[] }>
    (`/api/metrics/timeseries/agents?metric=${metric}&hours=${hours}`);

// System
export const fetchSystemResources = () => apiFetch<SystemResources>('/api/system/resources');
export const fetchSystemHealth = () => apiFetch<Record<string, unknown>>('/api/system/health');
export const fetchDevices = () => apiFetch<DeviceInfo[]>('/api/devices');

// Sessions (basic)
export const fetchSessions = () => apiFetch<{ sessions: SessionInfo[] }>('/api/sessions');

// Sessions management
export const fetchSessionsList = (agent?: string) =>
  apiFetch<{ sessions: any[] }>(`/api/sessions/list${agent ? `?agent=${agent}` : ''}`);
export const fetchSessionUsage = (id: string, agent?: string) =>
  apiFetch<any>(`/api/sessions/${id}/usage${agent ? `?agent=${agent}` : ''}`);
export const patchSession = (id: string, data: any, agent?: string) =>
  apiPatch<{ status: string }>(`/api/sessions/${id}${agent ? `?agent=${agent}` : ''}`, data);
export const deleteSession = (id: string, agent?: string) =>
  apiDelete<{ status: string }>(`/api/sessions/${id}${agent ? `?agent=${agent}` : ''}`);
export const fetchSessionHistory = (id: string, agent?: string) =>
  apiFetch<{ messages: any[] }>(`/api/sessions/${id}/history${agent ? `?agent=${agent}` : ''}`);
export const fetchSessionsUsageTimeseries = (agent?: string) =>
  apiFetch<any>(`/api/sessions/usage/timeseries${agent ? `?agent=${agent}` : ''}`);

// Discovery
export const fetchDiscovery = () => apiFetch<DiscoveryResult>('/api/discovery');
export const refreshDiscovery = () => apiPost<{ status: string }>('/api/discovery/refresh', {});
export const fetchPipelines = () => apiFetch<{ pipelines: Pipeline[] }>('/api/pipelines');
export const fetchAgents = () => apiFetch<{ agents: Agent[] }>('/api/agents');
export const fetchSkills = (params?: { category?: string; search?: string; page?: number; limit?: number }) => {
  const q = new URLSearchParams();
  if (params?.category) q.set('category', params.category);
  if (params?.search) q.set('search', params.search);
  if (params?.page) q.set('page', String(params.page));
  if (params?.limit) q.set('limit', String(params.limit));
  return apiFetch<{ skills: SkillInfo[]; total: number; page: number }>(`/api/skills?${q}`);
};
export const fetchSkillCategories = () => apiFetch<{ categories: SkillCategory[] }>('/api/skills/categories');
export const fetchSkillDetail = (name: string) => apiFetch<SkillInfo>(`/api/skills/${name}`);
export const fetchAgentDetail = (name: string) => apiFetch<AgentDetail>(`/api/agents/${name}`);

// Channels
export const fetchChannels = () => apiFetch<{ channels: ChannelConfig[] }>('/api/channels');
export const updateChannel = (id: string, data: Partial<ChannelConfig>) =>
  apiPut<{ status: string; channel: ChannelConfig }>(`/api/channels/${id}`, data);
export const createChannel = (data: ChannelConfig) =>
  apiPost<{ status: string; channel: ChannelConfig }>('/api/channels', data);
export const deleteChannel = (id: string) => apiDelete<{ status: string }>(`/api/channels/${id}`);

// Logs
export const fetchLogFiles = () => apiFetch<{ files: LogFile[] }>('/api/logs/files');
export const fetchLogTail = (file: string, lines = 100) =>
  apiFetch<{ lines: string[]; total: number }>(`/api/logs/tail?file=${encodeURIComponent(file)}&lines=${lines}`);

// Chat
export const sendChatMessage = (message: string) =>
  apiPost<Record<string, unknown>>('/api/chat', { message });

// Health
export const fetchHealth = () => apiFetch<{ status: string }>('/health');

// Config
export const fetchConfig = () => apiFetch<ConfigData>('/api/config');
export const fetchConfigSchema = () => apiFetch<any>('/api/config/schema');
export const updateConfig = (data: any) => apiPut<{ status: string }>('/api/config', data);
export const applyConfig = () => apiPost<{ status: string }>('/api/config/apply', {});
export const fetchModels = () => apiFetch<{ models: any[] }>('/api/models');

// Nodes & Devices
export const fetchNodes = () => apiFetch<{ nodes: any[] }>('/api/nodes');
export const fetchNodeDevices = () => apiFetch<{ devices: any[] }>('/api/nodes/devices');
export const approveDevice = (id: string) => apiPost<{ status: string }>(`/api/nodes/devices/${id}/approve`, {});
export const rejectDevice = (id: string) => apiPost<{ status: string }>(`/api/nodes/devices/${id}/reject`, {});
export const revokeDevice = (id: string) => apiPost<{ status: string }>(`/api/nodes/devices/${id}/revoke`, {});
export const rotateDeviceToken = (id: string) => apiPost<{ status: string }>(`/api/nodes/devices/${id}/rotate`, {});

// Projects
export const fetchProjects = (agent: string) =>
  apiFetch<{ agent: string; projects: ProjectInfo[] }>(`/api/projects?agent=${agent}`);
export const fetchProjectTree = (agent: string, project: string) =>
  apiFetch<FileNode>(`/api/projects/${agent}/${encodeURIComponent(project)}/tree`);
export const fetchProjectFile = (agent: string, path: string) =>
  apiFetch<{ name: string; content: string | null; size: number }>(`/api/projects/${agent}/file?path=${encodeURIComponent(path)}`);

// Debug
export const fetchDebugHealth = (agent?: string) =>
  apiFetch<any>(`/api/debug/health${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugStatus = (agent?: string) =>
  apiFetch<any>(`/api/debug/status${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugPresence = (agent?: string) =>
  apiFetch<any>(`/api/debug/presence${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugGateway = (agent?: string) =>
  apiFetch<GatewayStatus>(`/api/debug/gateway${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugSessions = (agent?: string) =>
  apiFetch<{ sessions: any[] }>(`/api/debug/sessions${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugLogs = (agent?: string) =>
  apiFetch<{ lines: string[] }>(`/api/debug/logs${agent ? `?agent=${agent}` : ''}`);
export const fetchDebugFilesystem = (agent?: string) =>
  apiFetch<{ checks: Record<string, any> }>(`/api/debug/filesystem${agent ? `?agent=${agent}` : ''}`);

import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { fetchAgentDetail } from '../api/endpoints';
import type { AgentDetail } from '../api/types';
import EmptyState from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';
import {
  Code, Search, PenTool, Settings, Shield, DollarSign, Bot,
  ChevronDown, ChevronUp, Folder, Cpu, Wrench, FileText, Users,
  Wifi, WifiOff, Loader2,
} from 'lucide-react';
import { AGENTS } from '../constants/agents';

const iconMap: Record<string, any> = {
  code: Code,
  search: Search,
  'pen-tool': PenTool,
  settings: Settings,
  shield: Shield,
  'dollar-sign': DollarSign,
  bot: Bot,
};

// Map workspace labels to AGENTS constant colors
function getAgentDotColor(name: string): string {
  const match = AGENTS.find(a => a.id === name || a.name.toLowerCase() === name.toLowerCase());
  return match?.dot || 'bg-slate-400';
}

type Tab = 'overview' | 'workspace' | 'tools';

interface ExpandedState {
  detail: AgentDetail | null;
  loading: boolean;
  tab: Tab;
}

export default function AgentsPage() {
  const { agents, fetchAgents } = useStore();
  const [expanded, setExpanded] = useState<Record<string, ExpandedState>>({});

  useEffect(() => { fetchAgents(); }, []);

  const toggleExpand = async (agentName: string) => {
    if (expanded[agentName] && !expanded[agentName].loading) {
      // Collapse
      setExpanded(prev => {
        const next = { ...prev };
        delete next[agentName];
        return next;
      });
      return;
    }

    // Expand — fetch detail
    setExpanded(prev => ({
      ...prev,
      [agentName]: { detail: null, loading: true, tab: 'overview' },
    }));

    try {
      const detail = await fetchAgentDetail(agentName);
      setExpanded(prev => ({
        ...prev,
        [agentName]: { detail, loading: false, tab: 'overview' },
      }));
    } catch {
      setExpanded(prev => ({
        ...prev,
        [agentName]: { detail: null, loading: false, tab: 'overview' },
      }));
    }
  };

  const setTab = (agentName: string, tab: Tab) => {
    setExpanded(prev => ({
      ...prev,
      [agentName]: { ...prev[agentName], tab },
    }));
  };

  if (agents.length === 0) return <EmptyState message="No agents discovered" />;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Agents</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {agents.map((a, i) => {
          const Icon = iconMap[a.icon] || Bot;
          const isExpanded = !!expanded[a.name];
          const state = expanded[a.name];
          const dotColor = getAgentDotColor(a.name);

          return (
            <div key={i} className={`${isExpanded ? 'md:col-span-2 xl:col-span-4' : ''}`}>
              {/* Card */}
              <div
                onClick={() => toggleExpand(a.name)}
                className={`bg-slate-800/50 rounded-xl border transition-colors cursor-pointer ${
                  isExpanded
                    ? 'border-slate-600 rounded-b-none'
                    : 'border-slate-700/50 hover:border-slate-600'
                }`}
              >
                <div className="p-5">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg" style={{ backgroundColor: a.color + '20', color: a.color }}>
                      <Icon size={20} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-white font-semibold truncate">{a.name}</h3>
                        <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span className="capitalize">{a.type}</span>
                        {a.model && a.model !== 'unknown' && (
                          <>
                            <span className="text-slate-600">|</span>
                            <span>{a.model}</span>
                          </>
                        )}
                        {a.port && (
                          <>
                            <span className="text-slate-600">|</span>
                            <span>:{a.port}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <StatusBadge status={a.status} />
                      {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                    </div>
                  </div>
                  {!isExpanded && a.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {a.capabilities.slice(0, 4).map((c, j) => (
                        <span key={j} className="px-2 py-0.5 text-xs bg-slate-700/50 text-slate-300 rounded">{c}</span>
                      ))}
                      {a.capabilities.length > 4 && (
                        <span className="px-2 py-0.5 text-xs bg-slate-700/50 text-slate-500 rounded">+{a.capabilities.length - 4}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="bg-slate-800/30 border border-t-0 border-slate-600 rounded-b-xl">
                  {state?.loading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 size={24} className="animate-spin text-slate-400" />
                      <span className="ml-2 text-slate-400">Loading agent details...</span>
                    </div>
                  ) : (
                    <>
                      {/* Tabs */}
                      <div className="flex border-b border-slate-700/50 px-5">
                        {([
                          { key: 'overview' as Tab, label: 'Overview', icon: FileText },
                          { key: 'workspace' as Tab, label: 'Workspace', icon: Folder },
                          { key: 'tools' as Tab, label: 'Tools', icon: Wrench },
                        ]).map(({ key, label, icon: TabIcon }) => (
                          <button
                            key={key}
                            onClick={(e) => { e.stopPropagation(); setTab(a.name, key); }}
                            className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                              state?.tab === key
                                ? 'border-blue-400 text-blue-400'
                                : 'border-transparent text-slate-400 hover:text-white'
                            }`}
                          >
                            <TabIcon size={14} />
                            {label}
                          </button>
                        ))}
                      </div>

                      {/* Tab Content */}
                      <div className="p-5">
                        {state?.tab === 'overview' && (
                          <div className="space-y-4">
                            {state.detail?.identity ? (
                              <div>
                                <h4 className="text-sm font-medium text-slate-300 mb-2">Identity / Role</h4>
                                <div className="bg-slate-900/50 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-wrap max-h-64 overflow-y-auto">
                                  {state.detail.identity}
                                </div>
                              </div>
                            ) : (
                              <p className="text-sm text-slate-500 italic">No IDENTITY.md found in workspace</p>
                            )}
                            {a.capabilities.length > 0 && (
                              <div>
                                <h4 className="text-sm font-medium text-slate-300 mb-2">Capabilities</h4>
                                <div className="flex flex-wrap gap-1.5">
                                  {a.capabilities.map((c, j) => (
                                    <span key={j} className="px-2.5 py-1 text-xs bg-slate-700/50 text-slate-300 rounded-md">{c}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            <div>
                              <h4 className="text-sm font-medium text-slate-300 mb-2">Sub-agents</h4>
                              <div className="flex items-center gap-2 text-sm text-slate-500">
                                <Users size={14} />
                                <span>No active sub-agents</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {state?.tab === 'workspace' && (
                          <div className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <h4 className="text-sm font-medium text-slate-300 mb-1">Workspace Path</h4>
                                <p className="text-sm text-slate-400 font-mono bg-slate-900/50 rounded px-3 py-2 break-all">
                                  {state.detail?.workspace || a.config_path || 'N/A'}
                                </p>
                              </div>
                              <div>
                                <h4 className="text-sm font-medium text-slate-300 mb-1">Gateway Status</h4>
                                <div className="flex items-center gap-2 text-sm">
                                  {state.detail?.gateway_available === true ? (
                                    <><Wifi size={14} className="text-emerald-400" /><span className="text-emerald-400">Available (port {a.port})</span></>
                                  ) : state.detail?.gateway_available === false ? (
                                    <><WifiOff size={14} className="text-red-400" /><span className="text-red-400">Unreachable (port {a.port})</span></>
                                  ) : (
                                    <><Cpu size={14} className="text-slate-500" /><span className="text-slate-500">No port configured</span></>
                                  )}
                                </div>
                              </div>
                            </div>
                            {state.detail?.workspace_config && (
                              <div>
                                <h4 className="text-sm font-medium text-slate-300 mb-2">Config</h4>
                                <pre className="bg-slate-900/50 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto max-h-64">
                                  {JSON.stringify(state.detail.workspace_config, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        )}

                        {state?.tab === 'tools' && (
                          <div>
                            {state.detail?.tools && state.detail.tools.length > 0 ? (
                              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
                                {state.detail.tools.map((tool, j) => (
                                  <div key={j} className="flex items-center gap-2 bg-slate-900/50 rounded-lg px-3 py-2">
                                    <Wrench size={12} className="text-slate-500 shrink-0" />
                                    <span className="text-sm text-slate-300 truncate">{tool.name}</span>
                                    <span className="ml-auto text-xs text-slate-500 capitalize shrink-0">{tool.category}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-slate-500 italic">No shared skills found</p>
                            )}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

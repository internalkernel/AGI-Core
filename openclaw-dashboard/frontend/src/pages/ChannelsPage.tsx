import { useEffect, useState } from 'react';
import { fetchChannels, updateChannel } from '../api/endpoints';
import type { ChannelConfig } from '../api/types';
import { AGENTS } from '../constants/agents';
import {
  MessageSquare, Gamepad2, Phone, Send, Shield, Mail, MessageCircle,
  ChevronDown, ChevronUp, Loader2, ToggleLeft, ToggleRight, X,
} from 'lucide-react';

const channelIcons: Record<string, any> = {
  slack: MessageSquare,
  discord: Gamepad2,
  whatsapp: Phone,
  telegram: Send,
  signal: Shield,
  email: Mail,
  sms: MessageCircle,
  'message-square': MessageSquare,
};

const channelColors: Record<string, string> = {
  slack: '#4A154B',
  discord: '#5865F2',
  whatsapp: '#25D366',
  telegram: '#0088CC',
  signal: '#3A76F0',
  email: '#EA4335',
  sms: '#10b981',
};

export default function ChannelsPage() {
  const [channels, setChannels] = useState<ChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [agentPickerFor, setAgentPickerFor] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    loadChannels();
  }, []);

  const loadChannels = async () => {
    try {
      const res = await fetchChannels();
      setChannels(res.channels);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const toggleEnabled = async (ch: ChannelConfig) => {
    setUpdating(ch.id);
    try {
      const res = await updateChannel(ch.id, { enabled: !ch.enabled });
      setChannels(prev => prev.map(c => c.id === ch.id ? { ...c, ...res.channel } : c));
    } catch {
      // silently fail
    } finally {
      setUpdating(null);
    }
  };

  const toggleAgentAccess = async (channelId: string, agentId: string) => {
    const ch = channels.find(c => c.id === channelId);
    if (!ch) return;

    const newAgents = ch.agents.includes(agentId)
      ? ch.agents.filter(a => a !== agentId)
      : [...ch.agents, agentId];

    setUpdating(channelId);
    try {
      const res = await updateChannel(channelId, { agents: newAgents });
      setChannels(prev => prev.map(c => c.id === channelId ? { ...c, ...res.channel } : c));
    } catch {
      // silently fail
    } finally {
      setUpdating(null);
    }
  };

  // Show channels that are always_show or enabled
  const visibleChannels = channels.filter(ch => ch.always_show || ch.enabled);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={24} className="animate-spin text-slate-400" />
        <span className="ml-2 text-slate-400">Loading channels...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">Channels</h1>
      <p className="text-sm text-slate-400">Configure communication channels and assign agent access.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {visibleChannels.map(ch => {
          const Icon = channelIcons[ch.icon] || MessageSquare;
          const color = channelColors[ch.id] || '#6366f1';
          const isExpanded = expandedId === ch.id;
          const isUpdating = updating === ch.id;

          return (
            <div key={ch.id} className={`${isExpanded ? 'md:col-span-2 xl:col-span-3' : ''}`}>
              <div className={`bg-slate-800/50 rounded-xl border transition-colors ${
                isExpanded ? 'border-slate-600 rounded-b-none' : 'border-slate-700/50 hover:border-slate-600'
              }`}>
                <div className="p-5">
                  {/* Header */}
                  <div className="flex items-center gap-3 mb-3">
                    <div className="p-2 rounded-lg" style={{ backgroundColor: color + '20', color }}>
                      <Icon size={20} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-white font-semibold">{ch.name}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        ch.enabled
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-slate-700/50 text-slate-500'
                      }`}>
                        {ch.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <button
                      onClick={() => toggleEnabled(ch)}
                      disabled={isUpdating}
                      className="text-slate-400 hover:text-white transition-colors disabled:opacity-50"
                      title={ch.enabled ? 'Disable channel' : 'Enable channel'}
                    >
                      {ch.enabled
                        ? <ToggleRight size={28} className="text-emerald-400" />
                        : <ToggleLeft size={28} />
                      }
                    </button>
                  </div>

                  {/* Agent Access Dots */}
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-xs text-slate-500 mr-1">Agents:</span>
                    {ch.agents.length > 0 ? (
                      ch.agents.map(agentId => {
                        const agentInfo = AGENTS.find(a => a.id === agentId);
                        return (
                          <span
                            key={agentId}
                            title={agentInfo?.name || agentId}
                            className={`w-3 h-3 rounded-full ${agentInfo?.dot || 'bg-slate-400'}`}
                          />
                        );
                      })
                    ) : (
                      <span className="text-xs text-slate-600">None assigned</span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setAgentPickerFor(agentPickerFor === ch.id ? null : ch.id);
                      }}
                      className="ml-1 text-xs text-slate-500 hover:text-blue-400 transition-colors"
                    >
                      Edit
                    </button>
                  </div>

                  {/* Agent Picker */}
                  {agentPickerFor === ch.id && (
                    <div className="bg-slate-900/50 rounded-lg p-3 mb-2 space-y-1.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-slate-300">Toggle Agent Access</span>
                        <button onClick={() => setAgentPickerFor(null)} className="text-slate-500 hover:text-white">
                          <X size={14} />
                        </button>
                      </div>
                      {AGENTS.map(agent => {
                        const hasAccess = ch.agents.includes(agent.id);
                        return (
                          <button
                            key={agent.id}
                            onClick={() => toggleAgentAccess(ch.id, agent.id)}
                            disabled={isUpdating}
                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors ${
                              hasAccess
                                ? 'bg-slate-700/50 text-white'
                                : 'text-slate-400 hover:bg-slate-800'
                            } disabled:opacity-50`}
                          >
                            <span className={`w-2.5 h-2.5 rounded-full ${agent.dot}`} />
                            <span>{agent.name}</span>
                            {hasAccess && <span className="ml-auto text-xs text-emerald-400">Active</span>}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Expand/Collapse Config */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : ch.id)}
                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {isExpanded ? 'Hide config' : 'Show config'}
                  </button>
                </div>
              </div>

              {/* Expanded Config */}
              {isExpanded && (
                <div className="bg-slate-800/30 border border-t-0 border-slate-600 rounded-b-xl p-5">
                  <h4 className="text-sm font-medium text-slate-300 mb-3">Channel Configuration</h4>
                  {Object.keys(ch.config).length > 0 ? (
                    <div className="space-y-2">
                      {Object.entries(ch.config).map(([key, value]) => (
                        <div key={key} className="flex items-center gap-2">
                          <span className="text-xs text-slate-500 min-w-[100px]">{key}:</span>
                          <span className="text-sm text-slate-300">{String(value) || '(not set)'}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500 italic">No configuration fields</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {visibleChannels.length === 0 && (
        <div className="text-center py-12 text-slate-500">
          <MessageSquare size={40} className="mx-auto mb-3 opacity-50" />
          <p>No channels configured. Add channels via the API.</p>
        </div>
      )}
    </div>
  );
}

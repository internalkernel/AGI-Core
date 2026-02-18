import { useState, useRef, useEffect, useCallback } from 'react';
import { AGENTS } from '../constants/agents';
import type { ChatMessage } from '../api/types';
import { Send, Loader2, WifiOff, Columns2, Columns3, Columns4, Trash2 } from 'lucide-react';

/* ── Agent colour helpers ──────────────────────────────────────── */

const AGENT_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  'content-specialist': { bg: 'bg-teal-500/10', text: 'text-teal-400', border: 'border-teal-500/20' },
  'devops':             { bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/20' },
  'support-coordinator':{ bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' },
  'wealth-strategist':  { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/20' },
  'design-specialist':  { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20' },
};

const fallbackStyle = { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/20' };

function aStyle(id: string) { return AGENT_STYLE[id] || fallbackStyle; }
function aName(id: string)  { return AGENTS.find(a => a.id === id)?.name || id; }
function aDot(id: string)   { return AGENTS.find(a => a.id === id)?.dot || 'bg-slate-400'; }

/* ── localStorage helpers ──────────────────────────────────────── */

const MAX_STORED = 200;  // cap per channel to keep localStorage lean

function loadHistory(key: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw) as ChatMessage[];
  } catch { /* corrupt data — start fresh */ }
  return [];
}

function saveHistory(key: string, msgs: ChatMessage[]) {
  try {
    // only persist the last MAX_STORED non-system messages + recent system
    const trimmed = msgs.slice(-MAX_STORED);
    localStorage.setItem(key, JSON.stringify(trimmed));
  } catch { /* quota exceeded — silently skip */ }
}

/* ── ChatColumn — single-agent chat (used in column mode) ─────── */

function ChatColumn({
  agentId,
  onAgentChange,
  showAgentPicker,
}: {
  agentId: string;
  onAgentChange?: (id: string) => void;
  showAgentPicker?: boolean;
}) {
  const storageKey = `chat-agent-${agentId}`;
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadHistory(storageKey));
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [sending, setSending] = useState(false);
  const streamingRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  /* persist on change */
  useEffect(() => { saveHistory(storageKey, messages); }, [messages, storageKey]);

  /* auto-scroll */
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /* WebSocket lifecycle */
  useEffect(() => {
    setConnected(false);
    streamingRef.current = null;
    setSending(false);

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(
      `${proto}//${window.location.host}/ws/chat?agent=${agentId}`,
    );

    socket.onopen = () => setConnected(true);

    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === 'connection_error') {
          setMessages(prev => [...prev, {
            id: crypto.randomUUID(), role: 'system', content: data.error,
            timestamp: Date.now(), agent: agentId,
          }]);
          return;
        }

        if (data.type === 'system') return;

        if (data.type === 'delta') {
          if (!streamingRef.current) {
            const newId = crypto.randomUUID();
            streamingRef.current = newId;
            setMessages(prev => [...prev, {
              id: newId, role: 'assistant', content: data.content,
              timestamp: Date.now(), agent: data.agent || agentId,
            }]);
          } else {
            setMessages(prev => {
              const updated = [...prev];
              if (updated.length > 0) {
                const last = { ...updated[updated.length - 1] };
                last.content += data.content;
                updated[updated.length - 1] = last;
              }
              return updated;
            });
          }
          return;
        }

        if (data.type === 'message' || data.type === 'done') {
          streamingRef.current = null;
          setSending(false);
        }
      } catch { /* ignore */ }
    };

    socket.onerror = () => setConnected(false);
    socket.onclose = () => {
      setConnected(false);
      streamingRef.current = null;
      setSending(false);
    };

    wsRef.current = socket;
    return () => { socket.close(); wsRef.current = null; };
  }, [agentId]);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  const resetHeight = () => {
    const el = inputRef.current;
    if (el) { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 150)}px`; }
  };

  const sendMessage = () => {
    if (!input.trim() || sending) return;
    const text = input;
    setInput('');
    setSending(true);
    streamingRef.current = null;
    if (inputRef.current) { inputRef.current.style.height = 'auto'; }

    setMessages(prev => [...prev, {
      id: crypto.randomUUID(), role: 'user', content: text,
      timestamp: Date.now(), agent: agentId,
    }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content: text }));
    } else {
      setSending(false);
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'system',
        content: 'Not connected \u2014 try again in a moment',
        timestamp: Date.now(), agent: agentId,
      }]);
    }
  };

  const clearHistory = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(storageKey);
  }, [storageKey]);

  const style = aStyle(agentId);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Agent picker + clear */}
      {showAgentPicker && onAgentChange && (
        <div className="flex items-center gap-1 mb-2">
          <div className="flex gap-1 flex-wrap flex-1">
            {AGENTS.map(a => {
              const s = aStyle(a.id);
              return (
                <button key={a.id} onClick={() => onAgentChange(a.id)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                    a.id === agentId
                      ? `${s.bg} ${s.text} border ${s.border}`
                      : 'text-slate-500 hover:text-slate-300 border border-transparent'
                  }`}>
                  <span className={`w-2 h-2 rounded-full ${a.dot}`} />
                  <span className="truncate">{a.name}</span>
                </button>
              );
            })}
          </div>
          {messages.length > 0 && (
            <button onClick={clearHistory} title="Clear history"
              className="p-1 rounded text-slate-500 hover:text-rose-400 transition-colors shrink-0">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      )}

      {!connected && (
        <div className="flex items-center gap-1.5 text-xs text-amber-400 mb-2">
          <WifiOff size={12} />
          <span>Connecting to {aName(agentId)}&hellip;</span>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 bg-slate-800/30 rounded-xl border border-slate-700/50 overflow-y-auto p-3 space-y-2 mb-2 min-h-0">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-xs text-slate-500">
              {connected ? `Chat with ${aName(agentId)}` : 'Connecting\u2026'}
            </p>
          </div>
        )}

        {messages.map(msg => {
          const ms = msg.agent ? aStyle(msg.agent) : style;
          return (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 ${
                msg.role === 'user'
                  ? 'text-white'
                  : msg.role === 'system'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : `${ms.bg} border ${ms.border} text-slate-200`
              }`} style={msg.role === 'user' ? { backgroundColor: '#223d81' } : undefined}>
                {msg.role === 'system' && (
                  <div className="text-[10px] opacity-60 mb-0.5">system</div>
                )}
                <div className="text-sm whitespace-pre-wrap break-words">{msg.content}</div>
              </div>
            </div>
          );
        })}

        {sending && !streamingRef.current && (
          <div className="flex justify-start">
            <div className={`${style.bg} border ${style.border} rounded-xl px-3 py-2`}>
              <Loader2 size={14} className="animate-spin text-slate-400" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); resetHeight(); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          placeholder={connected ? 'Type a message\u2026' : 'Connecting\u2026'}
          disabled={!connected}
          rows={1}
          className="flex-1 px-3 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 resize-none overflow-y-auto"
          style={{ maxHeight: 150 }}
        />
        <button onClick={sendMessage} disabled={sending || !connected}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 shrink-0">
          {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        </button>
      </div>
    </div>
  );
}

/* ── CollectiveColumn — true multi-agent shared context chat ──── */

const COLLECTIVE_KEY = 'chat-collective';

function CollectiveColumn() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadHistory(COLLECTIVE_KEY));
  const [input, setInput] = useState('');
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0].id);
  const [connected, setConnected] = useState(false);
  const [sending, setSending] = useState(false);
  const streamingRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  /* persist on change */
  useEffect(() => { saveHistory(COLLECTIVE_KEY, messages); }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /* single WS to the collective backend endpoint */
  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(
      `${proto}//${window.location.host}/ws/chat/collective`,
    );

    socket.onopen = () => setConnected(true);

    socket.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === 'connection_error') {
          setMessages(prev => [...prev, {
            id: crypto.randomUUID(), role: 'system', content: data.error,
            timestamp: Date.now(),
          }]);
          return;
        }

        if (data.type === 'system') {
          setMessages(prev => [...prev, {
            id: crypto.randomUUID(), role: 'system', content: data.content,
            timestamp: Date.now(),
          }]);
          return;
        }

        if (data.type === 'delta') {
          const agent = data.agent;
          if (!streamingRef.current) {
            const newId = crypto.randomUUID();
            streamingRef.current = newId;
            setMessages(prev => [...prev, {
              id: newId, role: 'assistant', content: data.content,
              timestamp: Date.now(), agent,
            }]);
          } else {
            setMessages(prev => {
              const updated = [...prev];
              if (updated.length > 0) {
                const last = { ...updated[updated.length - 1] };
                last.content += data.content;
                updated[updated.length - 1] = last;
              }
              return updated;
            });
          }
          return;
        }

        if (data.type === 'message') {
          streamingRef.current = null;
          setSending(false);
          return;
        }
        if (data.type === 'done') {
          streamingRef.current = null;
          setSending(false);
        }
      } catch { /* ignore */ }
    };

    socket.onerror = () => setConnected(false);
    socket.onclose = () => {
      setConnected(false);
      streamingRef.current = null;
      setSending(false);
    };

    wsRef.current = socket;
    return () => { socket.close(); wsRef.current = null; };
  }, []);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  const resetHeight = () => {
    const el = inputRef.current;
    if (el) { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 150)}px`; }
  };

  const sendMessage = () => {
    if (!input.trim() || sending) return;
    const text = input;
    setInput('');
    setSending(true);
    streamingRef.current = null;
    if (inputRef.current) { inputRef.current.style.height = 'auto'; }

    setMessages(prev => [...prev, {
      id: crypto.randomUUID(), role: 'user', content: text,
      timestamp: Date.now(), agent: selectedAgent,
    }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content: text, agent: selectedAgent }));
    } else {
      setSending(false);
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'system',
        content: 'Not connected \u2014 try again in a moment',
        timestamp: Date.now(),
      }]);
    }
  };

  const clearHistory = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(COLLECTIVE_KEY);
  }, []);

  const selStyle = aStyle(selectedAgent);

  return (
    <div className="flex flex-col h-full min-h-0">
      {!connected && (
        <div className="flex items-center gap-1.5 text-xs text-amber-400 mb-2">
          <WifiOff size={12} />
          <span>Connecting to collective chat&hellip;</span>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 bg-slate-800/30 rounded-xl border border-slate-700/50 overflow-y-auto p-3 space-y-2 mb-2 min-h-0">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-xs text-slate-500">
              Collective chat &mdash; all agents share context. Select an agent and send a message.
            </p>
          </div>
        )}

        {messages.map(msg => {
          const ms = msg.agent ? aStyle(msg.agent) : fallbackStyle;
          return (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 ${
                msg.role === 'user'
                  ? 'text-white'
                  : msg.role === 'system'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : `${ms.bg} border ${ms.border} text-slate-200`
              }`} style={msg.role === 'user' ? { backgroundColor: '#223d81' } : undefined}>
                {msg.role === 'assistant' && msg.agent && (
                  <div className={`text-[10px] font-semibold mb-0.5 ${aStyle(msg.agent).text}`}>
                    {aName(msg.agent)}
                  </div>
                )}
                {msg.role === 'user' && msg.agent && (
                  <div className="text-[10px] opacity-60 mb-0.5">
                    to {aName(msg.agent)}
                  </div>
                )}
                {msg.role === 'system' && (
                  <div className="text-[10px] opacity-60 mb-0.5">system</div>
                )}
                <div className="text-sm whitespace-pre-wrap break-words">{msg.content}</div>
              </div>
            </div>
          );
        })}

        {sending && !streamingRef.current && (
          <div className="flex justify-start">
            <div className={`${selStyle.bg} border ${selStyle.border} rounded-xl px-3 py-2`}>
              <Loader2 size={14} className="animate-spin text-slate-400" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input bar with agent selector + clear */}
      <div className="flex gap-2 items-end">
        <div className="flex gap-1 shrink-0">
          {AGENTS.map(a => {
            const s = aStyle(a.id);
            return (
              <button key={a.id} onClick={() => setSelectedAgent(a.id)} title={a.name}
                className={`flex items-center gap-1 px-2 py-2 rounded-lg text-xs transition-colors ${
                  a.id === selectedAgent
                    ? `${s.bg} ${s.text} border ${s.border}`
                    : 'text-slate-500 hover:text-slate-300 border border-transparent'
                }`}>
                <span className={`w-2 h-2 rounded-full ${aDot(a.id)}`} />
                <span className="hidden lg:inline truncate max-w-[90px]">{a.name}</span>
              </button>
            );
          })}
        </div>

        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); resetHeight(); }}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          placeholder={connected ? 'Type a message\u2026' : 'Connecting\u2026'}
          disabled={!connected}
          rows={1}
          className="flex-1 px-3 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 resize-none overflow-y-auto"
          style={{ maxHeight: 150 }}
        />

        <button onClick={sendMessage} disabled={sending || !connected}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50">
          {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        </button>

        {messages.length > 0 && (
          <button onClick={clearHistory} title="Clear history"
            className="p-2 rounded-lg text-slate-500 hover:text-rose-400 transition-colors shrink-0">
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

/* ── ChatPage ──────────────────────────────────────────────────── */

export default function ChatPage() {
  const [mode, setMode] = useState<'all' | 2 | 3 | 4>(() => {
    const saved = localStorage.getItem('chatCols');
    if (saved === '2' || saved === '3' || saved === '4') return Number(saved) as 2 | 3 | 4;
    return 'all';
  });

  const [columnAgents, setColumnAgents] = useState(() => AGENTS.map(a => a.id));

  const setModeAndSave = (m: 'all' | 2 | 3 | 4) => {
    setMode(m);
    localStorage.setItem('chatCols', m === 'all' ? 'all' : String(m));
  };

  const setColumnAgent = (idx: number, id: string) => {
    setColumnAgents(prev => {
      const next = [...prev];
      next[idx] = id;
      return next;
    });
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">Chat</h1>
          <button onClick={() => setModeAndSave('all')}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
              mode === 'all'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white border border-slate-700'
            }`}>
            All
          </button>
        </div>

        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700/50">
          {([2, 3, 4] as const).map(n => {
            const Icon = n === 2 ? Columns2 : n === 3 ? Columns3 : Columns4;
            return (
              <button key={n} onClick={() => setModeAndSave(n)}
                className={`p-1.5 rounded transition-colors ${
                  mode === n ? 'bg-blue-600/20 text-blue-400' : 'text-slate-500 hover:text-white'
                }`} title={`${n} columns`}>
                <Icon size={16} />
              </button>
            );
          })}
        </div>
      </div>

      {/* Chat area */}
      {mode === 'all' ? (
        <div className="flex-1 min-h-0">
          <CollectiveColumn />
        </div>
      ) : (
        <div className={`flex-1 min-h-0 grid gap-3 ${
          mode === 2 ? 'grid-cols-2' : mode === 3 ? 'grid-cols-3' : 'grid-cols-4'
        }`}>
          {Array.from({ length: mode }, (_, i) => (
            <ChatColumn
              key={`col-${i}-${columnAgents[i]}`}
              agentId={columnAgents[i] || AGENTS[i % AGENTS.length].id}
              onAgentChange={(id) => setColumnAgent(i, id)}
              showAgentPicker
            />
          ))}
        </div>
      )}
    </div>
  );
}

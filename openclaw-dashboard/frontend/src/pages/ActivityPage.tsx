import { useState, useEffect } from 'react';
import { Activity, LayoutGrid, Columns2, Columns3, Columns4 } from 'lucide-react';
import ActivityFeed from '../components/features/ActivityFeed';
import { fetchActivityStats } from '../api/activity';
import { AGENTS } from '../constants/agents';

const columnIcons = [LayoutGrid, Columns2, Columns3, Columns4];

function getStoredColumns(): number {
  try {
    const v = localStorage.getItem('activity-columns');
    if (v) {
      const n = parseInt(v, 10);
      if (n >= 1 && n <= 4) return n;
    }
  } catch {}
  return 1;
}

export default function ActivityPage() {
  const [stats, setStats] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<string>('all');
  const [agentFilter, setAgentFilter] = useState<string>('all');
  const [columns, setColumns] = useState<number>(getStoredColumns);
  const [columnAgents, setColumnAgents] = useState<string[]>(() => AGENTS.map(a => a.id));

  useEffect(() => {
    fetchActivityStats().then(setStats).catch(() => {});
  }, []);

  function handleColumnsChange(n: number) {
    setColumns(n);
    localStorage.setItem('activity-columns', String(n));
  }

  const categories = Object.keys(stats).filter((c) => c !== 'agent');
  const total = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity size={24} className="text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Activity Feed</h1>
          <span className="text-sm text-slate-400 bg-slate-800 px-2 py-0.5 rounded">{total} events</span>
        </div>

        {/* Column toggle */}
        <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700/50">
          {[1, 2, 3, 4].map((n) => {
            const Icon = columnIcons[n - 1];
            return (
              <button
                key={n}
                onClick={() => handleColumnsChange(n)}
                title={`${n} column${n > 1 ? 's' : ''}`}
                className={`p-1.5 rounded transition-colors ${
                  columns === n
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-slate-500 hover:text-white'
                }`}
              >
                <Icon size={16} />
              </button>
            );
          })}
        </div>
      </div>

      {/* Entity-type filter buttons (no "All" or "agent") */}
      <div className="flex gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => { setFilter(filter === cat ? 'all' : cat); setAgentFilter('all'); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filter === cat
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'bg-slate-800 text-slate-400 border border-slate-700/50 hover:text-white'
            }`}
          >
            {cat} {stats[cat] ? `(${stats[cat]})` : ''}
          </button>
        ))}
      </div>

      {/* Agent filter buttons — visible in single-column mode */}
      {columns === 1 && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setAgentFilter('all')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
              agentFilter === 'all'
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'bg-slate-800 text-slate-400 border border-slate-700/50 hover:text-white'
            }`}
          >
            All Agents
          </button>
          {AGENTS.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setAgentFilter(agent.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                agentFilter === agent.id
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700/50 hover:text-white'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${agent.dot}`} />
              {agent.name}
            </button>
          ))}
        </div>
      )}

      {/* Feed(s) */}
      {columns === 1 ? (
        <ActivityFeed
          entityType={filter !== 'all' ? filter : undefined}
          agentId={agentFilter !== 'all' ? agentFilter : undefined}
          limit={50}
        />
      ) : (
        <div
          className="gap-4"
          style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        >
          {Array.from({ length: columns }, (_, i) => {
            const agentId = columnAgents[i] || AGENTS[i % AGENTS.length].id;
            return (
              <div key={`col-${i}-${agentId}`} className="min-w-0">
                <div className="flex gap-1 flex-wrap mb-3">
                  {AGENTS.map(a => (
                    <button
                      key={a.id}
                      onClick={() => setColumnAgents(prev => {
                        const next = [...prev];
                        next[i] = a.id;
                        return next;
                      })}
                      className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                        a.id === agentId
                          ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                          : 'text-slate-500 hover:text-slate-300 border border-transparent'
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full ${a.dot}`} />
                      <span className="truncate">{a.name}</span>
                    </button>
                  ))}
                </div>
                <ActivityFeed
                  entityType="agent"
                  agentId={agentId}
                  limit={30}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

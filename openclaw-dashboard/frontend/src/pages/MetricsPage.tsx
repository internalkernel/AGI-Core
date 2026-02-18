import { useEffect, useState, useMemo } from 'react';
import { useStore } from '../store';
import { formatNumber } from '../utils/format';
import { Download } from 'lucide-react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { AGENTS } from '../constants/agents';

const MODEL_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
  '#ef4444', '#06b6d4', '#f97316', '#84cc16', '#a855f7',
  '#14b8a6', '#e11d48',
];

function colorForModel(index: number): string {
  return MODEL_COLORS[index % MODEL_COLORS.length];
}

const AGENT_COLORS: Record<string, string> = {
  'content-specialist': '#2dd4bf',  // teal-400
  'devops': '#818cf8',              // indigo-400
  'support-coordinator': '#fbbf24', // amber-400
  'wealth-strategist': '#fb7185',   // rose-400
  'design-specialist': '#c084fc',   // purple-400
};

function colorForAgent(id: string): string {
  return AGENT_COLORS[id] || '#94a3b8';
}

export default function MetricsPage() {
  const {
    timeseries, timeseriesModels, breakdown, fetchTimeseries, fetchBreakdown,
    agentTimeseries, agentTimeseriesNames, fetchAgentTimeseries,
  } = useStore();
  const [hours, setHours] = useState(168);
  const [metric, setMetric] = useState<'tokens' | 'cost'>('tokens');

  useEffect(() => {
    fetchTimeseries(metric, hours);
    fetchBreakdown();
    fetchAgentTimeseries(metric, hours);
  }, [metric, hours]);

  const totalTokens = breakdown?.by_model?.reduce((a, b) => a + b.tokens, 0) ?? 0;
  const totalCost = breakdown?.by_model?.reduce((a, b) => a + b.cost, 0) ?? 0;

  // Build per-model daily trend data from breakdown.daily_model
  const { dailyTrendData, dailyTrendModels } = useMemo(() => {
    const dm = breakdown?.daily_model;
    if (!dm || dm.length === 0) {
      return { dailyTrendData: breakdown?.daily_trend ?? [], dailyTrendModels: [] as string[] };
    }

    const models = new Set<string>();
    const pivot: Record<string, Record<string, number>> = {};
    for (const entry of dm) {
      models.add(entry.model);
      if (!pivot[entry.date]) pivot[entry.date] = {};
      pivot[entry.date][entry.model] = (pivot[entry.date][entry.model] || 0) +
        (metric === 'tokens' ? entry.tokens : entry.cost);
    }

    const sortedModels = Array.from(models).sort();
    const data = Object.keys(pivot).sort().map(date => {
      const point: Record<string, any> = { date };
      for (const m of sortedModels) {
        point[m] = pivot[date][m] || 0;
      }
      return point;
    });

    return { dailyTrendData: data, dailyTrendModels: sortedModels };
  }, [breakdown, metric]);

  // Determine models for the line chart
  const lineModels = timeseriesModels.length > 0 ? timeseriesModels : [];

  const exportCsv = () => {
    if (!breakdown?.by_model) return;
    const header = 'Model,Tokens,Cost,Requests\n';
    const rows = breakdown.by_model.map(m => `"${m.model}",${m.tokens},${m.cost},${m.requests}`).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'token-metrics.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Metrics</h1>
        <div className="flex items-center gap-3">
          <button onClick={exportCsv} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white" title="Export CSV">
            <Download size={16} />
          </button>
          <div className="flex gap-2">
            {[6, 12, 24, 48, 168].map((h) => (
              <button key={h} onClick={() => setHours(h)}
                className={`px-3 py-1 text-xs rounded-lg ${hours === h ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}>
                {h < 48 ? `${h}h` : `${h / 24}d`}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
          <div className="text-xs text-slate-400">Total Tokens</div>
          <div className="text-xl font-bold text-white mt-1">{formatNumber(totalTokens)}</div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
          <div className="text-xs text-slate-400">Total Cost</div>
          <div className="text-xl font-bold text-white mt-1">${totalCost.toFixed(2)}</div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
          <div className="text-xs text-slate-400">Models Used</div>
          <div className="text-xl font-bold text-white mt-1">{breakdown?.by_model?.length ?? 0}</div>
        </div>
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
          <div className="text-xs text-slate-400">Time Range</div>
          <div className="text-xl font-bold text-white mt-1">{hours < 48 ? `${hours}h` : `${hours / 24}d`}</div>
        </div>
      </div>

      <div className="flex gap-2">
        {(['tokens', 'cost'] as const).map((m) => (
          <button key={m} onClick={() => setMetric(m)}
            className={`px-4 py-1.5 text-sm rounded-lg capitalize ${metric === m ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'}`}>
            {m}
          </button>
        ))}
      </div>

      {/* Usage Over Time + Usage by Agent — side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">
            {metric === 'tokens' ? 'Token Usage' : 'Cost'} Over Time
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={timeseries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                itemStyle={{ fontSize: 12 }}
              />
              {lineModels.length > 0 ? (
                lineModels.map((model, i) => (
                  <Line
                    key={model}
                    type="monotone"
                    dataKey={model}
                    stroke={colorForModel(i)}
                    strokeWidth={2}
                    dot={false}
                    name={model}
                  />
                ))
              ) : (
                <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} name="Total" />
              )}
            </LineChart>
          </ResponsiveContainer>
          {lineModels.length > 0 && (
            <div className="flex flex-wrap gap-4 mt-3 justify-center">
              {lineModels.map((model, i) => (
                <div key={model} className="flex items-center gap-1.5 text-xs text-slate-300">
                  <div className="w-3 h-0.5 rounded" style={{ backgroundColor: colorForModel(i) }} />
                  {model}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Usage by Agent */}
        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Usage by Agent</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={agentTimeseries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                itemStyle={{ fontSize: 12 }}
              />
              {agentTimeseriesNames.map((agentId) => {
                const agent = AGENTS.find(a => a.id === agentId);
                return (
                  <Line
                    key={agentId}
                    type="monotone"
                    dataKey={agentId}
                    stroke={colorForAgent(agentId)}
                    strokeWidth={2}
                    dot={false}
                    name={agent?.name || agentId}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
          {agentTimeseriesNames.length > 0 && (
            <div className="flex flex-wrap gap-4 mt-3 justify-center">
              {agentTimeseriesNames.map((agentId) => {
                const agent = AGENTS.find(a => a.id === agentId);
                return (
                  <div key={agentId} className="flex items-center gap-1.5 text-xs text-slate-300">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForAgent(agentId) }} />
                    {agent?.name || agentId}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart — Usage by Model */}
        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Usage by Model</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={breakdown?.by_model ?? []} dataKey="tokens" nameKey="model" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2}>
                {(breakdown?.by_model ?? []).map((_, i) => (
                  <Cell key={i} fill={colorForModel(i)} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-2 justify-center">
            {(breakdown?.by_model ?? []).map((m, i) => (
              <div key={m.model} className="flex items-center gap-1.5 text-xs text-slate-300">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForModel(i) }} />
                {m.model}
              </div>
            ))}
          </div>
        </div>

        {/* Daily Trend — stacked bars per model */}
        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Daily Trend</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={dailyTrendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                itemStyle={{ fontSize: 12 }}
              />
              {dailyTrendModels.length > 0 ? (
                dailyTrendModels.map((model, i) => (
                  <Bar
                    key={model}
                    dataKey={model}
                    stackId="stack"
                    fill={colorForModel(i)}
                    radius={i === dailyTrendModels.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                    name={model}
                  />
                ))
              ) : (
                <Bar dataKey="tokens" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              )}
            </BarChart>
          </ResponsiveContainer>
          {dailyTrendModels.length > 0 && (
            <div className="flex flex-wrap gap-4 mt-3 justify-center">
              {dailyTrendModels.map((model, i) => (
                <div key={model} className="flex items-center gap-1.5 text-xs text-slate-300">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForModel(i) }} />
                  {model}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

    </div>
  );
}

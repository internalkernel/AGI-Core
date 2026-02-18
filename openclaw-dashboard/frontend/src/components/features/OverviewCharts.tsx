import { useStore } from '../../store';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { AGENTS } from '../../constants/agents';

const tooltipStyle = { backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: 8 };

const MODEL_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
  '#ef4444', '#06b6d4', '#f97316', '#84cc16', '#a855f7',
  '#14b8a6', '#e11d48',
];

function colorForModel(index: number): string {
  return MODEL_COLORS[index % MODEL_COLORS.length];
}

const AGENT_COLORS: Record<string, string> = {
  'content-specialist': '#2dd4bf',
  'devops': '#818cf8',
  'support-coordinator': '#fbbf24',
  'wealth-strategist': '#fb7185',
  'design-specialist': '#c084fc',
};

function colorForAgent(id: string): string {
  return AGENT_COLORS[id] || '#94a3b8';
}

export default function OverviewCharts() {
  const timeseries = useStore((s) => s.timeseries);
  const timeseriesModels = useStore((s) => s.timeseriesModels);
  const agentTimeseries = useStore((s) => s.agentTimeseries);
  const agentTimeseriesNames = useStore((s) => s.agentTimeseriesNames);
  const breakdown = useStore((s) => s.breakdown);

  const byModel = breakdown?.by_model ?? [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Token Usage — per-model lines */}
      <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Token Usage</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={timeseries}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#94a3b8' }}
              itemStyle={{ fontSize: 12 }}
            />
            {timeseriesModels.length > 0 ? (
              timeseriesModels.map((model, i) => (
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
        {timeseriesModels.length > 0 && (
          <div className="flex flex-wrap gap-4 mt-3 justify-center">
            {timeseriesModels.map((model, i) => (
              <div key={model} className="flex items-center gap-1.5 text-xs text-slate-300">
                <div className="w-3 h-0.5 rounded" style={{ backgroundColor: colorForModel(i) }} />
                {model}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Usage by Model — colored bars */}
      <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Usage by Model</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={byModel}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="model" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: '#94a3b8' }}
              itemStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="tokens" radius={[4, 4, 0, 0]}>
              {byModel.map((_, i) => (
                <Cell key={i} fill={colorForModel(i)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {byModel.length > 0 && (
          <div className="flex flex-wrap gap-4 mt-3 justify-center">
            {byModel.map((m, i) => (
              <div key={m.model} className="flex items-center gap-1.5 text-xs text-slate-300">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorForModel(i) }} />
                {m.model}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Usage by Agent — per-agent lines */}
      <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 lg:col-span-2">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Usage by Agent</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={agentTimeseries}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="label" stroke="#94a3b8" fontSize={11} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip
              contentStyle={tooltipStyle}
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
  );
}

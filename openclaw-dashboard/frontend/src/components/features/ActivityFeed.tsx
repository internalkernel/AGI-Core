import { useEffect, useState } from 'react';
import { Activity, Zap, Settings, Play, Users, Calendar } from 'lucide-react';
import type { ActivityItem } from '../../api/activity';
import { fetchActivities } from '../../api/activity';
import { useActivityStream } from '../../hooks/useActivityStream';

const iconMap: Record<string, typeof Activity> = {
  job: Zap,
  config: Settings,
  session: Users,
  discovery: Play,
  calendar: Calendar,
};

const colorMap: Record<string, string> = {
  job: 'text-blue-400 bg-blue-400/10',
  config: 'text-amber-400 bg-amber-400/10',
  session: 'text-green-400 bg-green-400/10',
  discovery: 'text-purple-400 bg-purple-400/10',
  calendar: 'text-pink-400 bg-pink-400/10',
  auth: 'text-red-400 bg-red-400/10',
};

function formatTime(ts: string): string {
  const d = new Date(ts);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString();
}

function formatEventType(t: string): string {
  return t.replace(/[._]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface Props {
  compact?: boolean;
  limit?: number;
}

export default function ActivityFeed({ compact = false, limit = 20 }: Props) {
  const { activities: streamActivities } = useActivityStream();
  const [dbActivities, setDbActivities] = useState<ActivityItem[]>([]);

  useEffect(() => {
    fetchActivities({ limit }).then(setDbActivities).catch(() => {});
  }, [limit]);

  // Merge: stream items first, then DB items (deduplicated)
  const streamIds = new Set(streamActivities.map((a) => a.id));
  const merged = [...streamActivities, ...dbActivities.filter((a) => !streamIds.has(a.id))].slice(0, limit);

  if (compact) {
    return (
      <div className="space-y-1">
        {merged.length === 0 && (
          <p className="text-sm text-slate-500 py-2">No recent activity</p>
        )}
        {merged.slice(0, 5).map((item) => {
          const color = colorMap[item.entity_type] || 'text-slate-400 bg-slate-400/10';
          return (
            <div key={item.id} className="flex items-center gap-2 py-1.5">
              <div className={`w-6 h-6 rounded flex items-center justify-center ${color}`}>
                {(() => { const Icon = iconMap[item.entity_type] || Activity; return <Icon size={12} />; })()}
              </div>
              <span className="text-xs text-slate-300 truncate flex-1">{formatEventType(item.event_type)}</span>
              <span className="text-xs text-slate-500">{formatTime(item.timestamp)}</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {merged.length === 0 && (
        <div className="text-center py-12">
          <Activity size={32} className="text-slate-600 mx-auto mb-2" />
          <p className="text-slate-500">No activity recorded yet</p>
          <p className="text-xs text-slate-600 mt-1">Events will appear here as agents perform actions</p>
        </div>
      )}
      {merged.map((item) => {
        const color = colorMap[item.entity_type] || 'text-slate-400 bg-slate-400/10';
        const Icon = iconMap[item.entity_type] || Activity;
        return (
          <div key={item.id} className="flex items-start gap-3 bg-slate-800/50 rounded-lg border border-slate-700/50 p-3">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${color}`}>
              <Icon size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">{formatEventType(item.event_type)}</span>
                {item.status && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    item.status === 'success' ? 'bg-green-500/20 text-green-400' :
                    item.status === 'error' ? 'bg-red-500/20 text-red-400' :
                    'bg-slate-500/20 text-slate-400'
                  }`}>{item.status}</span>
                )}
              </div>
              {item.entity_id && <p className="text-xs text-slate-400 mt-0.5">{item.entity_type}: {item.entity_id}</p>}
              {item.details && (
                <p className="text-xs text-slate-500 mt-1 truncate">{JSON.stringify(item.details).slice(0, 120)}</p>
              )}
            </div>
            <span className="text-xs text-slate-500 whitespace-nowrap">{formatTime(item.timestamp)}</span>
          </div>
        );
      })}
    </div>
  );
}

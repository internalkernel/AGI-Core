import { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';
import ActivityFeed from '../components/features/ActivityFeed';
import { fetchActivityStats } from '../api/activity';

export default function ActivityPage() {
  const [stats, setStats] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetchActivityStats().then(setStats).catch(() => {});
  }, []);

  const categories = ['all', ...Object.keys(stats)];
  const total = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity size={24} className="text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Activity Feed</h1>
          <span className="text-sm text-slate-400 bg-slate-800 px-2 py-0.5 rounded">{total} events</span>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filter === cat
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                : 'bg-slate-800 text-slate-400 border border-slate-700/50 hover:text-white'
            }`}
          >
            {cat === 'all' ? 'All' : cat} {cat !== 'all' && stats[cat] ? `(${stats[cat]})` : ''}
          </button>
        ))}
      </div>

      <ActivityFeed limit={50} />
    </div>
  );
}

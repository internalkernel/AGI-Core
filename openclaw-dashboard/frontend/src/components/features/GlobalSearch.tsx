import { useEffect, useRef } from 'react';
import { Search, X, Activity, Calendar, Bot, Wrench } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useGlobalSearch } from '../../hooks/useGlobalSearch';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function GlobalSearch({ open, onClose }: Props) {
  const { query, results, loading, search, clear } = useGlobalSearch();
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      clear();
    }
  }, [open, clear]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (open) onClose();
        // parent handles open
      }
      if (e.key === 'Escape' && open) {
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const hasResults = results && Object.values(results.results).some((arr) => arr && arr.length > 0);

  const goTo = (path: string) => {
    onClose();
    navigate(path);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-start justify-center pt-[20vh] z-50" onClick={onClose}>
      <div className="bg-slate-900 rounded-xl border border-slate-700/50 w-full max-w-lg shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700/50">
          <Search size={18} className="text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => search(e.target.value)}
            placeholder="Search activities, events, agents, skills..."
            className="flex-1 bg-transparent text-white text-sm outline-none placeholder-slate-500"
          />
          {query && (
            <button onClick={clear} className="text-slate-500 hover:text-white">
              <X size={16} />
            </button>
          )}
          <kbd className="hidden sm:inline text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">ESC</kbd>
        </div>

        {loading && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">Searching...</div>
        )}

        {!loading && query && !hasResults && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">No results found</div>
        )}

        {!loading && hasResults && (
          <div className="max-h-80 overflow-y-auto py-2">
            {results!.results.activities && results!.results.activities.length > 0 && (
              <div className="px-3 py-1">
                <div className="text-xs text-slate-500 font-medium px-1 py-1">Activities</div>
                {results!.results.activities.slice(0, 5).map((a: any) => (
                  <button key={a.id} onClick={() => goTo('/activity')} className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 text-left">
                    <Activity size={14} className="text-blue-400 shrink-0" />
                    <span className="text-sm text-slate-300 truncate">{a.event_type} — {a.entity_id || a.entity_type}</span>
                  </button>
                ))}
              </div>
            )}

            {results!.results.calendar && results!.results.calendar.length > 0 && (
              <div className="px-3 py-1">
                <div className="text-xs text-slate-500 font-medium px-1 py-1">Calendar Events</div>
                {results!.results.calendar.slice(0, 5).map((c: any) => (
                  <button key={c.id} onClick={() => goTo('/calendar')} className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 text-left">
                    <Calendar size={14} className="text-pink-400 shrink-0" />
                    <span className="text-sm text-slate-300 truncate">{c.title}</span>
                  </button>
                ))}
              </div>
            )}

            {results!.results.agents && results!.results.agents.length > 0 && (
              <div className="px-3 py-1">
                <div className="text-xs text-slate-500 font-medium px-1 py-1">Agents</div>
                {results!.results.agents.slice(0, 5).map((a: any, i: number) => (
                  <button key={i} onClick={() => goTo('/agents')} className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 text-left">
                    <Bot size={14} className="text-green-400 shrink-0" />
                    <span className="text-sm text-slate-300 truncate">{a.name || JSON.stringify(a).slice(0, 60)}</span>
                  </button>
                ))}
              </div>
            )}

            {results!.results.skills && results!.results.skills.length > 0 && (
              <div className="px-3 py-1">
                <div className="text-xs text-slate-500 font-medium px-1 py-1">Skills</div>
                {results!.results.skills.slice(0, 5).map((s: any, i: number) => (
                  <button key={i} onClick={() => goTo('/skills')} className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 text-left">
                    <Wrench size={14} className="text-amber-400 shrink-0" />
                    <span className="text-sm text-slate-300 truncate">{s.name || JSON.stringify(s).slice(0, 60)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {!query && (
          <div className="px-4 py-6 text-center text-xs text-slate-500">
            Type to search across activities, calendar events, agents, and skills
          </div>
        )}
      </div>
    </div>
  );
}

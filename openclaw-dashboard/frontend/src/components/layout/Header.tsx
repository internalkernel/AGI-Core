import { useStore } from '../../store';
import { useAuth } from '../../hooks/useAuth';
import { Activity, Search, LogOut } from 'lucide-react';

interface Props {
  onSearchClick?: () => void;
}

export default function Header({ onSearchClick }: Props) {
  const system = useStore((s) => s.system);
  const { user, logout } = useAuth();

  return (
    <header className="h-14 bg-slate-800/60 backdrop-blur border-b border-slate-700/50 flex items-center px-6 shrink-0">
      <div className="flex items-center gap-2">
        <Activity size={16} className="text-green-400" />
        <span className="text-sm text-slate-300">
          CPU {system?.cpu_percent.toFixed(0)}% | MEM {system?.memory_percent.toFixed(0)}% | DISK {system?.disk_percent.toFixed(0)}%
        </span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button
          onClick={onSearchClick}
          className="flex items-center gap-2 bg-slate-800 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
        >
          <Search size={14} />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden sm:inline text-[10px] bg-slate-700 px-1.5 py-0.5 rounded">⌘K</kbd>
        </button>
        {user && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">{user.username}</span>
            <button onClick={logout} className="text-slate-400 hover:text-white transition-colors p-1" title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

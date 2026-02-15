import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import ToastContainer from '../common/Toast';
import GlobalSearch from '../features/GlobalSearch';
import { useStore } from '../../store';
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts';

export default function Layout() {
  const fetchAll = useStore((s) => s.fetchAll);
  const [searchOpen, setSearchOpen] = useState(false);

  useKeyboardShortcuts();

  useEffect(() => { fetchAll(); }, []);

  // Cmd+K to open search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="h-screen flex bg-slate-950 text-slate-200 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header onSearchClick={() => setSearchOpen(true)} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}

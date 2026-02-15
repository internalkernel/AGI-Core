import { useState, useEffect, useMemo } from 'react';
import { Calendar, ChevronLeft, ChevronRight, Plus, X } from 'lucide-react';
import {
  fetchCalendarEvents, createCalendarEvent, deleteCalendarEvent,
  type CalendarEvent, type CalendarEventCreate,
} from '../api/calendar';

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

export default function CalendarPage() {
  const [current, setCurrent] = useState(() => new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CalendarEventCreate>({
    title: '', start_time: '', end_time: '', description: '',
  });

  const year = current.getFullYear();
  const month = current.getMonth();
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);

  useEffect(() => {
    const start = new Date(year, month, 1).toISOString();
    const end = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
    fetchCalendarEvents(start, end).then(setEvents).catch(() => {});
  }, [year, month]);

  const eventsByDay = useMemo(() => {
    const map: Record<number, CalendarEvent[]> = {};
    events.forEach((e) => {
      const d = new Date(e.start_time).getDate();
      if (!map[d]) map[d] = [];
      map[d].push(e);
    });
    return map;
  }, [events]);

  const prevMonth = () => setCurrent(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrent(new Date(year, month + 1, 1));

  const handleCreate = async () => {
    if (!form.title || !form.start_time) return;
    await createCalendarEvent(form);
    setShowForm(false);
    setForm({ title: '', start_time: '', end_time: '', description: '' });
    // Refresh
    const start = new Date(year, month, 1).toISOString();
    const end = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
    fetchCalendarEvents(start, end).then(setEvents).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteCalendarEvent(id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  const today = new Date();
  const isToday = (day: number) => day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar size={24} className="text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Calendar</h1>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-3 py-1.5 rounded-lg transition-colors"
        >
          <Plus size={16} /> New Event
        </button>
      </div>

      {/* Month navigation */}
      <div className="flex items-center gap-4">
        <button onClick={prevMonth} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
          <ChevronLeft size={20} />
        </button>
        <h2 className="text-lg font-semibold text-white min-w-[200px] text-center">
          {current.toLocaleDateString('en', { month: 'long', year: 'numeric' })}
        </h2>
        <button onClick={nextMonth} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Calendar grid */}
      <div className="bg-slate-900 rounded-xl border border-slate-700/50 overflow-hidden">
        <div className="grid grid-cols-7 border-b border-slate-700/50">
          {days.map((d) => (
            <div key={d} className="py-2 text-center text-xs font-medium text-slate-500">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {Array.from({ length: firstDay }).map((_, i) => (
            <div key={`empty-${i}`} className="min-h-[100px] border-b border-r border-slate-800/50" />
          ))}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const day = i + 1;
            const dayEvents = eventsByDay[day] || [];
            return (
              <div key={day} className={`min-h-[100px] border-b border-r border-slate-800/50 p-1.5 ${isToday(day) ? 'bg-blue-600/5' : ''}`}>
                <div className={`text-xs font-medium mb-1 ${isToday(day) ? 'text-blue-400' : 'text-slate-400'}`}>{day}</div>
                {dayEvents.slice(0, 3).map((ev) => (
                  <div
                    key={ev.id}
                    className={`text-[10px] px-1 py-0.5 rounded mb-0.5 truncate ${
                      ev.source === 'google'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-blue-500/20 text-blue-400'
                    }`}
                    title={ev.title}
                  >
                    {ev.title}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className="text-[10px] text-slate-500">+{dayEvents.length - 3} more</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Event list for current month */}
      {events.length > 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Events this month</h3>
          <div className="space-y-2">
            {events.map((ev) => {
              const d = new Date(ev.start_time);
              return (
                <div key={ev.id} className="flex items-center gap-3 py-1.5">
                  <div className={`w-2 h-2 rounded-full ${ev.source === 'google' ? 'bg-green-500' : 'bg-blue-500'}`} />
                  <span className="text-sm text-white flex-1">{ev.title}</span>
                  <span className="text-xs text-slate-400">
                    {d.toLocaleDateString('en', { month: 'short', day: 'numeric' })}
                    {!ev.all_day && ` ${d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}`}
                  </span>
                  {ev.source === 'dashboard' && (
                    <button onClick={() => handleDelete(ev.id)} className="text-slate-500 hover:text-red-400">
                      <X size={14} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Create event modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-900 rounded-xl border border-slate-700/50 p-6 w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">New Event</h3>
            <div className="space-y-3">
              <input
                placeholder="Event title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="datetime-local"
                value={form.start_time?.slice(0, 16) || ''}
                onChange={(e) => setForm({ ...form, start_time: new Date(e.target.value).toISOString() })}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="datetime-local"
                value={form.end_time?.slice(0, 16) || ''}
                onChange={(e) => setForm({ ...form, end_time: new Date(e.target.value).toISOString() })}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="End time (optional)"
              />
              <textarea
                placeholder="Description (optional)"
                value={form.description || ''}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-20"
              />
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-white">Cancel</button>
              <button onClick={handleCreate} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg">Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

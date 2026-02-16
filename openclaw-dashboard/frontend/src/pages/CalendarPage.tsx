import { useState, useEffect, useMemo } from 'react';
import {
  Calendar, ChevronLeft, ChevronRight, Plus, X,
  LayoutGrid, List, CalendarDays,
} from 'lucide-react';
import {
  fetchCalendarEvents, createCalendarEvent, deleteCalendarEvent,
  type CalendarEvent, type CalendarEventCreate,
} from '../api/calendar';
import { AGENTS } from '../constants/agents';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function getWeekDates(date: Date): Date[] {
  const day = date.getDay();
  const start = new Date(date);
  start.setDate(start.getDate() - day);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

function getAgentColor(agentId: string | null | undefined): string {
  if (!agentId) return 'bg-blue-500';
  const match = AGENTS.find(a => a.id === agentId);
  return match?.dot || 'bg-blue-500';
}

function getAgentBgClass(agentId: string | null | undefined): string {
  if (!agentId) return 'bg-blue-500/20 text-blue-400';
  const match = AGENTS.find(a => a.id === agentId);
  if (!match) return 'bg-blue-500/20 text-blue-400';
  // Convert dot class to bg/text variant
  const base = match.dot.replace('bg-', '');
  return `bg-${base}/20 text-${base}`;
}

function eventDisplayClass(ev: CalendarEvent): string {
  if (ev.source === 'google') return 'bg-slate-400/20 text-slate-400';
  return getAgentBgClass(ev.agent);
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = 'monthly' | 'weekly' | 'agenda';
type FilterKey = 'all' | 'google' | string; // 'all', 'google', or agent id

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CalendarPage() {
  const [current, setCurrent] = useState(() => new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [view, setView] = useState<ViewMode>('monthly');
  const [filter, setFilter] = useState<FilterKey>('all');
  const [form, setForm] = useState<CalendarEventCreate>({
    title: '', start_time: '', end_time: '', description: '', agent: '', sync_to_google: false,
  });

  const year = current.getFullYear();
  const month = current.getMonth();
  const today = new Date();

  // Fetch events when month/year changes
  useEffect(() => {
    let start: string, end: string;
    if (view === 'weekly') {
      const weekDates = getWeekDates(current);
      start = weekDates[0].toISOString();
      end = new Date(weekDates[6].getFullYear(), weekDates[6].getMonth(), weekDates[6].getDate(), 23, 59, 59).toISOString();
    } else {
      start = new Date(year, month, 1).toISOString();
      end = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
    }
    fetchCalendarEvents(start, end).then(setEvents).catch(() => {});
  }, [year, month, view, current.toDateString()]);

  // Apply filter
  const filteredEvents = useMemo(() => {
    if (filter === 'all') return events;
    if (filter === 'google') return events.filter(e => e.source === 'google');
    return events.filter(e => e.agent === filter);
  }, [events, filter]);

  // Events grouped by day number (for monthly view)
  const eventsByDay = useMemo(() => {
    const map: Record<number, CalendarEvent[]> = {};
    filteredEvents.forEach((e) => {
      const d = new Date(e.start_time);
      if (d.getMonth() === month && d.getFullYear() === year) {
        const day = d.getDate();
        if (!map[day]) map[day] = [];
        map[day].push(e);
      }
    });
    return map;
  }, [filteredEvents, month, year]);

  // Navigation
  const navigate = (dir: -1 | 1) => {
    if (view === 'weekly') {
      const d = new Date(current);
      d.setDate(d.getDate() + dir * 7);
      setCurrent(d);
    } else {
      setCurrent(new Date(year, month + dir, 1));
    }
  };

  // Create event
  const handleCreate = async () => {
    if (!form.title || !form.start_time) return;
    await createCalendarEvent(form);
    setShowForm(false);
    setForm({ title: '', start_time: '', end_time: '', description: '', agent: '', sync_to_google: false });
    // Refresh
    const start = new Date(year, month, 1).toISOString();
    const end = new Date(year, month + 1, 0, 23, 59, 59).toISOString();
    fetchCalendarEvents(start, end).then(setEvents).catch(() => {});
  };

  const handleDelete = async (id: string) => {
    await deleteCalendarEvent(id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  const isToday = (day: number) => day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);

  // Heading text
  const headingText = view === 'weekly'
    ? (() => {
        const week = getWeekDates(current);
        const s = week[0], e = week[6];
        if (s.getMonth() === e.getMonth()) {
          return `${s.toLocaleDateString('en', { month: 'long' })} ${s.getDate()} – ${e.getDate()}, ${s.getFullYear()}`;
        }
        return `${s.toLocaleDateString('en', { month: 'short' })} ${s.getDate()} – ${e.toLocaleDateString('en', { month: 'short' })} ${e.getDate()}, ${e.getFullYear()}`;
      })()
    : current.toLocaleDateString('en', { month: 'long', year: 'numeric' });

  return (
    <div className="space-y-4">
      {/* Header row */}
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

      {/* Filter bar + view selector */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-1.5 flex-1">
          <FilterButton active={filter === 'all'} onClick={() => setFilter('all')}>All</FilterButton>
          {AGENTS.map(a => (
            <FilterButton
              key={a.id}
              active={filter === a.id}
              onClick={() => setFilter(a.id)}
              dotClass={a.dot}
            >
              {a.name}
            </FilterButton>
          ))}
          <FilterButton
            active={filter === 'google'}
            onClick={() => setFilter('google')}
            dotClass="bg-slate-400"
          >
            Google
          </FilterButton>
        </div>

        {/* View selector */}
        <div className="flex items-center bg-slate-800 rounded-lg p-0.5">
          {([
            { key: 'monthly' as ViewMode, icon: LayoutGrid, label: 'Month' },
            { key: 'weekly' as ViewMode, icon: CalendarDays, label: 'Week' },
            { key: 'agenda' as ViewMode, icon: List, label: 'Agenda' },
          ]).map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                view === key
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
          <ChevronLeft size={20} />
        </button>
        <h2 className="text-lg font-semibold text-white min-w-[280px] text-center">{headingText}</h2>
        <button onClick={() => navigate(1)} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white">
          <ChevronRight size={20} />
        </button>
      </div>

      {/* Views */}
      {view === 'monthly' && (
        <MonthlyView
          daysInMonth={daysInMonth}
          firstDay={firstDay}
          dayNames={dayNames}
          eventsByDay={eventsByDay}
          isToday={isToday}
        />
      )}

      {view === 'weekly' && (
        <WeeklyView
          current={current}
          dayNames={dayNames}
          filteredEvents={filteredEvents}
          today={today}
        />
      )}

      {view === 'agenda' && (
        <AgendaView
          events={filteredEvents}
          onDelete={handleDelete}
        />
      )}

      {/* Events list (monthly/weekly only) */}
      {view !== 'agenda' && filteredEvents.length > 0 && (
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">
            Events {view === 'weekly' ? 'this week' : 'this month'}
          </h3>
          <div className="space-y-2">
            {filteredEvents.map((ev) => {
              const d = new Date(ev.start_time);
              const agentInfo = AGENTS.find(a => a.id === ev.agent);
              return (
                <div key={ev.id} className="flex items-center gap-3 py-1.5">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${ev.source === 'google' ? 'bg-slate-400' : getAgentColor(ev.agent)}`} />
                  <span className="text-sm text-white flex-1 truncate">{ev.title}</span>
                  {agentInfo && (
                    <span className="text-xs text-slate-500">{agentInfo.name}</span>
                  )}
                  {ev.source === 'google' && (
                    <span className="text-xs text-slate-400">Google</span>
                  )}
                  <span className="text-xs text-slate-400 shrink-0">
                    {d.toLocaleDateString('en', { month: 'short', day: 'numeric' })}
                    {!ev.all_day && ` ${d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}`}
                  </span>
                  {ev.source === 'dashboard' && (
                    <button onClick={() => handleDelete(ev.id)} className="text-slate-500 hover:text-red-400 shrink-0">
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

              {/* Agent selector */}
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Agent (optional)</label>
                <select
                  value={form.agent || ''}
                  onChange={(e) => setForm({ ...form, agent: e.target.value || undefined })}
                  className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">No agent</option>
                  {AGENTS.map(a => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              {/* Sync to Google Calendar */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.sync_to_google || false}
                  onChange={(e) => setForm({ ...form, sync_to_google: e.target.checked })}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                />
                <span className="text-sm text-slate-300">Sync to Google Calendar</span>
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => { setShowForm(false); setForm({ title: '', start_time: '', end_time: '', description: '', agent: '', sync_to_google: false }); }}
                className="px-4 py-2 text-sm text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button onClick={handleCreate} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg">
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter Button
// ---------------------------------------------------------------------------

function FilterButton({
  active, onClick, dotClass, children,
}: {
  active: boolean;
  onClick: () => void;
  dotClass?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
        active
          ? 'bg-slate-700 text-white ring-1 ring-slate-500'
          : 'bg-slate-800/50 text-slate-400 hover:text-white hover:bg-slate-800'
      }`}
    >
      {dotClass && <span className={`w-2 h-2 rounded-full ${dotClass}`} />}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Monthly View
// ---------------------------------------------------------------------------

function MonthlyView({
  daysInMonth, firstDay, dayNames, eventsByDay, isToday,
}: {
  daysInMonth: number;
  firstDay: number;
  dayNames: string[];
  eventsByDay: Record<number, CalendarEvent[]>;
  isToday: (day: number) => boolean;
}) {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="grid grid-cols-7 border-b border-slate-700/50">
        {dayNames.map((d) => (
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
                  className={`text-[10px] px-1 py-0.5 rounded mb-0.5 truncate ${eventDisplayClass(ev)}`}
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
  );
}

// ---------------------------------------------------------------------------
// Weekly View
// ---------------------------------------------------------------------------

function WeeklyView({
  current, dayNames, filteredEvents, today,
}: {
  current: Date;
  dayNames: string[];
  filteredEvents: CalendarEvent[];
  today: Date;
}) {
  const weekDates = getWeekDates(current);
  const hours = Array.from({ length: 16 }, (_, i) => i + 7); // 7am to 10pm

  // Group events by day of the week
  const eventsByWeekday = useMemo(() => {
    const map: Record<number, CalendarEvent[]> = {};
    weekDates.forEach((d, idx) => {
      map[idx] = filteredEvents.filter(ev => isSameDay(new Date(ev.start_time), d));
    });
    return map;
  }, [filteredEvents, weekDates.map(d => d.toDateString()).join()]);

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-700/50 overflow-hidden">
      {/* Day headers */}
      <div className="grid grid-cols-[60px_repeat(7,1fr)] border-b border-slate-700/50">
        <div className="py-2" />
        {weekDates.map((d, i) => {
          const isCurrentDay = isSameDay(d, today);
          return (
            <div key={i} className={`py-2 text-center border-l border-slate-800/50 ${isCurrentDay ? 'bg-blue-600/5' : ''}`}>
              <div className="text-[10px] text-slate-500">{dayNames[i]}</div>
              <div className={`text-sm font-semibold ${isCurrentDay ? 'text-blue-400' : 'text-slate-300'}`}>{d.getDate()}</div>
            </div>
          );
        })}
      </div>

      {/* Time grid */}
      <div className="max-h-[600px] overflow-y-auto">
        {hours.map(hour => (
          <div key={hour} className="grid grid-cols-[60px_repeat(7,1fr)] min-h-[48px]">
            <div className="text-[10px] text-slate-500 text-right pr-2 pt-1 border-r border-slate-800/50">
              {hour === 0 ? '12 AM' : hour <= 12 ? `${hour} ${hour < 12 ? 'AM' : 'PM'}` : `${hour - 12} PM`}
            </div>
            {weekDates.map((d, dayIdx) => {
              const dayEvs = (eventsByWeekday[dayIdx] || []).filter(ev => {
                const evHour = new Date(ev.start_time).getHours();
                return evHour === hour;
              });
              return (
                <div key={dayIdx} className={`border-l border-b border-slate-800/50 p-0.5 ${isSameDay(d, today) ? 'bg-blue-600/5' : ''}`}>
                  {dayEvs.map(ev => (
                    <div
                      key={ev.id}
                      className={`text-[10px] px-1 py-0.5 rounded truncate ${eventDisplayClass(ev)}`}
                      title={ev.title}
                    >
                      {ev.title}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agenda View
// ---------------------------------------------------------------------------

function AgendaView({
  events,
  onDelete,
}: {
  events: CalendarEvent[];
  onDelete: (id: string) => void;
}) {
  // Group events by date
  const grouped = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    events.forEach(ev => {
      const key = new Date(ev.start_time).toLocaleDateString('en', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
      if (!map[key]) map[key] = [];
      map[key].push(ev);
    });
    return map;
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <Calendar size={40} className="mx-auto mb-3 opacity-50" />
        <p>No events to display</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([dateLabel, dayEvents]) => (
        <div key={dateLabel} className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-700/50 bg-slate-800/30">
            <h3 className="text-sm font-semibold text-slate-300">{dateLabel}</h3>
          </div>
          <div className="divide-y divide-slate-700/30">
            {dayEvents.map(ev => {
              const d = new Date(ev.start_time);
              const agentInfo = AGENTS.find(a => a.id === ev.agent);
              return (
                <div key={ev.id} className="flex items-center gap-3 px-5 py-3">
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${ev.source === 'google' ? 'bg-slate-400' : getAgentColor(ev.agent)}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white">{ev.title}</div>
                    {ev.description && (
                      <div className="text-xs text-slate-500 truncate mt-0.5">{ev.description}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {agentInfo && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${agentInfo.dot.replace('bg-', 'bg-')}/20 text-slate-400`}>
                        {agentInfo.name}
                      </span>
                    )}
                    {ev.source === 'google' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-400/20 text-slate-400">
                        Google
                      </span>
                    )}
                    <span className="text-xs text-slate-400">
                      {ev.all_day ? 'All day' : d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}
                      {ev.end_time && !ev.all_day && (
                        <> – {new Date(ev.end_time).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}</>
                      )}
                    </span>
                    {ev.source === 'dashboard' && (
                      <button onClick={() => onDelete(ev.id)} className="text-slate-500 hover:text-red-400">
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

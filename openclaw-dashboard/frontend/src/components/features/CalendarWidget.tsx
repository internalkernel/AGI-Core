import { useEffect, useState } from 'react';
import { Calendar } from 'lucide-react';
import { fetchCalendarEvents, type CalendarEvent } from '../../api/calendar';

export default function CalendarWidget() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);

  useEffect(() => {
    const now = new Date();
    const start = now.toISOString();
    const end = new Date(now.getTime() + 7 * 86400000).toISOString();
    fetchCalendarEvents(start, end).then(setEvents).catch(() => {});
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Calendar size={14} />
          Upcoming Events
        </h3>
        <a href="/calendar" className="text-xs text-blue-400 hover:text-blue-300">View all</a>
      </div>
      {events.length === 0 ? (
        <p className="text-xs text-slate-500 py-2">No upcoming events</p>
      ) : (
        <div className="space-y-2">
          {events.slice(0, 4).map((ev) => {
            const d = new Date(ev.start_time);
            return (
              <div key={ev.id} className="flex items-center gap-3">
                <div className="text-center w-10">
                  <div className="text-xs text-slate-500">{d.toLocaleDateString('en', { month: 'short' })}</div>
                  <div className="text-lg font-bold text-white leading-tight">{d.getDate()}</div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{ev.title}</p>
                  <p className="text-xs text-slate-500">
                    {ev.all_day ? 'All day' : d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}
                    {ev.source === 'google' && ' · Google'}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

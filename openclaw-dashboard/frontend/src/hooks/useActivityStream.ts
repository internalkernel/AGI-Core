import { useEffect, useRef, useState, useCallback } from 'react';
import type { ActivityItem } from '../api/activity';
import { wsUrl } from '../api/client';

export function useActivityStream() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const addActivity = useCallback((item: ActivityItem) => {
    setActivities((prev) => [item, ...prev].slice(0, 100));
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/activity'));
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send('ping'); // initial handshake
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'activity' && msg.data) {
          addActivity(msg.data);
        }
      } catch {}
    };

    ws.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
      }, 3000);
    };

    // Keep-alive ping every 30s
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [addActivity]);

  return { activities, setActivities };
}

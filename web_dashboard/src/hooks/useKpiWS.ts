import { useEffect, useRef } from 'react';
import { useFleetStore } from '../store/useFleetStore';

export function useKpiWS() {
  const updateKpis = useFleetStore((s) => s.updateKpis);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/kpis`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) {
          ws.close();
          return;
        }
        console.log('[KpiWS] Connected to /ws/kpis');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateKpis(data);
        } catch (e) {
          console.error('[KpiWS] Message parse error:', e);
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        console.warn('[KpiWS] Disconnected, reconnecting in 2s...');
        reconnectTimeoutRef.current = window.setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.error('[KpiWS] Socket error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [updateKpis]);
}

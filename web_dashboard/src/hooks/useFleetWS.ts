import { useEffect, useRef } from 'react';
import { useFleetStore } from '../store/useFleetStore';

export function useFleetWS() {
  const updateFleet = useFleetStore((s) => s.updateFleet);
  const setWsStatus = useFleetStore((s) => s.setWsStatus);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/fleet`;

      setWsStatus('CONNECTING');
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) {
          ws.close();
          return;
        }
        setWsStatus('CONNECTED');
        console.log('[FleetWS] Connected to /ws/fleet');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateFleet(data);
        } catch (e) {
          console.error('[FleetWS] Message parse error:', e);
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setWsStatus('DISCONNECTED');
        console.warn('[FleetWS] Disconnected, reconnecting in 2s...');
        reconnectTimeoutRef.current = window.setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.error('[FleetWS] Socket error:', err);
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
  }, [updateFleet, setWsStatus]);
}

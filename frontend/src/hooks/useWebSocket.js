import { useRef, useCallback, useEffect } from 'react';

export function useWebSocket(onComplete, onError) {
  const wsRef = useRef(null);
  const pingRef = useRef(null);

  const stop = useCallback(() => {
    if (pingRef.current) {
      clearInterval(pingRef.current);
      pingRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const start = useCallback(
    (sessionId, onTick) => {
      stop();

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/progress/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Keep alive ping every 25s
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return;

          if (data.type === 'completed' || data.status === 'completed') {
            onTick(data);
            onComplete(data);
            stop();
          } else if (data.type === 'error' || data.status === 'error') {
            onError(data.error || 'Processing error');
            stop();
          } else {
            // progress or init
            onTick(data);
          }
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        // Fallback: WebSocket failed, caller should handle
      };

      ws.onclose = () => {
        if (pingRef.current) {
          clearInterval(pingRef.current);
          pingRef.current = null;
        }
      };
    },
    [onComplete, onError, stop]
  );

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { start, stop };
}

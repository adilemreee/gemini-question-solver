import { useRef, useCallback } from 'react';
import { api } from '../lib/api';

export function useProgress(onComplete, onError) {
  const timerRef = useRef(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const start = useCallback(
    (sessionId, onTick) => {
      stop();
      const poll = async () => {
        try {
          const data = await api.getProgress(sessionId);
          onTick(data);
          if (data.status === 'completed') {
            onComplete(data);
          } else if (data.status === 'error') {
            onError(data.error || 'Processing error');
          } else {
            timerRef.current = setTimeout(poll, 800);
          }
        } catch (err) {
          timerRef.current = setTimeout(poll, 2000);
        }
      };
      poll();
    },
    [onComplete, onError, stop]
  );

  return { start, stop };
}

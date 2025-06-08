import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_BASE_URL, RECONNECT_INTERVAL_MS, MAX_RECONNECT_ATTEMPTS } from '../config';

interface UseWebSocketOptions {
  path: string;
  onMessage: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (event: Event) => void;
  reconnectInterval?: number; // in milliseconds
  maxRetries?: number;
}

const useWebSocket = ({
  path,
  onMessage,
  onConnect,
  onDisconnect,
  onError,
  reconnectInterval = RECONNECT_INTERVAL_MS,
  maxRetries = MAX_RECONNECT_ATTEMPTS,
}: UseWebSocketOptions) => {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const retryCount = useRef(0);
  const reconnectTimeout = useRef<number | null>(null); // Changed NodeJS.Timeout to number

  const connect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (retryCount.current >= maxRetries) {
      console.warn(`WebSocket: Max reconnect attempts (${maxRetries}) reached for ${path}. Aborting.`);
      return;
    }

    const socket = new WebSocket(`${WS_BASE_URL}${path}`);

    socket.onopen = () => {
      console.log(`WebSocket: Connected to ${path}`);
      setIsConnected(true);
      retryCount.current = 0; // Reset retry count on successful connection
      onConnect?.();
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('WebSocket: Failed to parse message data:', e);
        onMessage(event.data); // Pass raw data if parsing fails
      }
    };

    socket.onclose = (event) => {
      console.log(`WebSocket: Disconnected from ${path}`, event.code, event.reason);
      setIsConnected(false);
      onDisconnect?.();

      // Attempt to reconnect
      if (!event.wasClean && retryCount.current < maxRetries) {
        retryCount.current++;
        console.log(`WebSocket: Attempting to reconnect in ${reconnectInterval / 1000}s (attempt ${retryCount.current}/${maxRetries})...`);
        reconnectTimeout.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };

    socket.onerror = (event) => {
      console.error(`WebSocket: Error on ${path}:`, event);
      onError?.(event);
      socket.close(); // Close socket to trigger onclose and reconnect logic
    };

    ws.current = socket;
  }, [path, onMessage, onConnect, onDisconnect, onError, reconnectInterval, maxRetries]);

  useEffect(() => {
    connect();

    return () => {
      if (ws.current) {
        console.log(`WebSocket: Cleaning up connection for ${path}`);
        ws.current.close(1000, 'Component unmounted');
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect, path]); // Re-run effect if 'connect' changes (which it won't due to useCallback) or path changes

  return { isConnected, ws: ws.current };
};

export default useWebSocket;

import { useEffect, useState, useRef, useCallback } from 'react';
import { WS_BASE_URL } from '../config'; // Import WS_BASE_URL from config

interface UseWebSocketOptions {
  path: string;
  onMessage: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (event: Event) => void;
  reconnectInterval?: number; // in milliseconds
  maxRetries?: number;
}

const defaultReconnectInterval = 3000; // 3 seconds
const defaultMaxRetries = 5;

const useWebSocket = (options: UseWebSocketOptions) => {
  const {
    path,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = defaultReconnectInterval,
    maxRetries = defaultMaxRetries,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  // Use ReturnType<typeof setTimeout> for browser-compatible type
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);
  const isMounted = useRef(true); // To track if component is mounted

  const getWebSocketUrl = useCallback(() => {
    // Use WS_BASE_URL from config.ts directly
    const baseWsUrl = WS_BASE_URL;
    
    // Ensure the path starts with a slash and baseWsUrl doesn't end with one if path is absolute
    const fullPath = path.startsWith('/') ? path : `/${path}`;
    const finalUrl = `${baseWsUrl}${fullPath}`;
    
    console.log(`Attempting to connect to WebSocket: ${finalUrl}`);
    return finalUrl;
  }, [path]);

  const connect = useCallback(() => {
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return; // Already connected or connecting
    }

    if (retryCount.current >= maxRetries) {
      console.warn(`Max WebSocket reconnection retries (${maxRetries}) reached. Aborting.`);
      return;
    }

    const url = getWebSocketUrl();
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      if (isMounted.current) { // Only update state if component is mounted
        console.log('WebSocket connected');
        setIsConnected(true);
        retryCount.current = 0; // Reset retry count on successful connection
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
          reconnectTimeout.current = null;
        }
        onConnect?.();
      }
    };

    ws.current.onmessage = (event) => {
      if (isMounted.current) { // Only process message if component is mounted
        onMessage(event.data);
      }
    };

    ws.current.onclose = (event) => {
      if (isMounted.current) { // Only update state if component is mounted
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        onDisconnect?.();

        // Attempt to reconnect
        if (reconnectTimeout.current) {
          clearTimeout(reconnectTimeout.current);
        }
        retryCount.current += 1;
        console.log(`Attempting to reconnect WebSocket in ${reconnectInterval / 1000}s (Attempt ${retryCount.current}/${maxRetries})...`);
        reconnectTimeout.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };

    ws.current.onerror = (event) => {
      if (isMounted.current) { // Only update state if component is mounted
        console.error('WebSocket error:', event);
        onError?.(event);
        ws.current?.close(); // Close to trigger onclose and reconnect logic
      }
    };
  }, [getWebSocketUrl, onMessage, onConnect, onDisconnect, onError, reconnectInterval, maxRetries]);

  useEffect(() => {
    isMounted.current = true; // Set to true on mount
    connect();

    return () => {
      isMounted.current = false; // Set to false on unmount
      // Clean up on unmount
      if (ws.current) {
        ws.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect]);

  return { isConnected };
};

export default useWebSocket;

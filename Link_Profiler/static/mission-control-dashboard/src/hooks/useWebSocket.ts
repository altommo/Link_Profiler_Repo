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
  const reconnectTimeout = useRef<number | null>(null);

  // Store callbacks in refs to ensure stable references for useCallback
  // This prevents the 'connect' function from being re-created unnecessarily
  // when the parent component re-renders and provides new callback instances.
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  // Update refs whenever the props change to ensure the latest callbacks are used
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onConnectRef.current = onConnect;
  }, [onConnect]);

  useEffect(() => {
    onDisconnectRef.current = onDisconnect;
  }, [onDisconnect]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);


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
      onConnectRef.current?.(); // Use ref for callback
    };

    socket.onmessage = (event) => {
      try {
        // Debug: Log the raw event data
        console.log('WebSocket: Raw message received:', typeof event.data, event.data);
        
        // Always try to parse as JSON since WebSocket sends strings
        const data = JSON.parse(event.data);
        console.log('WebSocket: Parsed JSON successfully:', data);

        // Handle heartbeat messages separately
        if (data && data.type === 'heartbeat') {
          console.log('WebSocket: Received heartbeat.');
          // Do not pass heartbeat to onMessage as it's for connection maintenance
        } else {
          onMessageRef.current(data); // Use ref for callback for actual data
        }
      } catch (e) {
        console.error('WebSocket: Failed to parse message data:', e);
        console.error('WebSocket: Raw data was:', event.data);
        console.error('WebSocket: Data type was:', typeof event.data);
        // Try to pass the raw string if JSON parsing fails, but only if it's not a heartbeat
        // If it's a non-JSON heartbeat, it will still be passed. This is acceptable for now.
        onMessageRef.current(event.data); // Use ref for callback
      }
    };

    socket.onclose = (event) => {
      console.log(`WebSocket: Disconnected from ${path}`, event.code, event.reason);
      setIsConnected(false);
      onDisconnectRef.current?.(); // Use ref for callback

      // Attempt to reconnect if the disconnection was not clean and max retries not reached
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
      onErrorRef.current?.(event); // Use ref for callback
      socket.close(); // Close socket to trigger onclose and reconnect logic
    };

    ws.current = socket;
  }, [path, maxRetries, reconnectInterval]); // Dependencies are now stable (no callback props)

  useEffect(() => {
    connect();

    return () => {
      if (ws.current) {
        console.log(`WebSocket: Cleaning up connection for ${path}`);
        // Use code 1000 (Normal Closure) when component unmounts to prevent unwanted reconnects
        ws.current.close(1000, 'Component unmounted');
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect, path]); // This effect will now only re-run if 'connect' or 'path' truly change

  return { isConnected, ws: ws.current };
};

export default useWebSocket;

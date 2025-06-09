import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_BASE_URL, RECONNECT_INTERVAL_MS, MAX_RECONNECT_ATTEMPTS } from '../config';

interface UseWebSocketOptions {
  path: string;
  /**
   * Callback function to handle incoming messages.
   * This function will receive the message data already parsed as a JavaScript object.
   * It should NOT attempt to call JSON.parse() on the received data.
   */
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
      let parsedData: any;
      try {
        // Debug: Log the raw event data
        console.log('WebSocket: Raw message received:', typeof event.data, event.data);
        
        // Always try to parse as JSON since WebSocket sends strings
        parsedData = JSON.parse(event.data);
        console.log('WebSocket: Parsed JSON successfully:', parsedData);

        // Handle heartbeat messages separately
        if (parsedData && parsedData.type === 'heartbeat') {
          console.log('WebSocket: Received heartbeat.');
          // Do not pass heartbeat to onMessage as it's for connection maintenance
        } else {
          // Call the consumer's onMessage callback with the parsed data
          try {
            onMessageRef.current(parsedData);
          } catch (callbackError) {
            console.error('WebSocket: Error in onMessage callback:', callbackError);
            console.error('WebSocket: Data passed to callback was:', parsedData);
            // Re-throw or handle as appropriate, but for now, just log.
          }
        }
      } catch (e) {
        // This catch block handles errors from JSON.parse(event.data)
        console.error('WebSocket: Failed to parse incoming message data as JSON:', e);
        console.error('WebSocket: Raw data that caused parse error was:', event.data);
        console.error('WebSocket: Data type was:', typeof event.data);
        // If JSON parsing failed, we do not pass the raw string to onMessage by default,
        // as onMessage is expected to receive parsed data.
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

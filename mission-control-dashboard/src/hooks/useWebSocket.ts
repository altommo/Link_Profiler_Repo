import { useEffect, useState, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

interface UseWebSocketOptions {
  path: string;
  onMessage: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: any) => void;
}

const useWebSocket = ({ path, onMessage, onConnect, onDisconnect, onError }: UseWebSocketOptions) => {
  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (socketRef.current && socketRef.current.connected) {
      return;
    }

    const newSocket = io(path, {
      path,
      transports: ['websocket'],
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    newSocket.on('connect', () => {
      setIsConnected(true);
      onConnect?.();
      console.log(`WebSocket connected to ${path}`);
    });

    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      onDisconnect?.();
      console.log(`WebSocket disconnected from ${path}: ${reason}`);
    });

    newSocket.on('connect_error', (error) => {
      onError?.(error);
      console.error(`WebSocket connection error for ${path}:`, error);
    });

    newSocket.on('message', (data) => {
      onMessage(data);
    });

    socketRef.current = newSocket;
  }, [path, onMessage, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return { isConnected, socket: socketRef.current, connect, disconnect };
};

export default useWebSocket;

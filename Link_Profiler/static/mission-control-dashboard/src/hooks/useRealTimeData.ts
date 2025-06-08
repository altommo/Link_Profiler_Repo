import { useEffect } from 'react';
import useWebSocket from './useWebSocket';
import useMissionControlStore from '../stores/missionControlStore';

const useRealTimeData = () => {
  const setData = useMissionControlStore((state) => state.setData);

  const handleMessage = (message: any) => {
    try {
      // The message from FastAPI's model_dump_json() is already a stringified JSON.
      // We need to parse it once more here.
      const parsedData = JSON.parse(message);
      setData(parsedData);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };

  const { isConnected } = useWebSocket({
    path: '/ws/mission-control', // This path is proxied by Vite to your FastAPI backend
    onMessage: handleMessage,
    onConnect: () => console.log('Connected to Mission Control WebSocket'),
    onDisconnect: () => console.log('Disconnected from Mission Control WebSocket'),
    onError: (error) => console.error('Mission Control WebSocket Error:', error),
  });

  useEffect(() => {
    if (!isConnected) {
      console.warn('Mission Control WebSocket is not connected. Real-time data will not be updated.');
    }
  }, [isConnected]);

  return { isConnected };
};

export default useRealTimeData;

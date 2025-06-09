import { useEffect } from 'react';
import useWebSocket from './useWebSocket';
import useMissionControlStore from '../stores/missionControlStore';

const useRealTimeData = () => {
  const setData = useMissionControlStore((state) => state.setData);

  const handleMessage = (message: any) => {
    try {
      // The message from useWebSocket is already a parsed JavaScript object.
      // No need to call JSON.parse() here.
      setData(message); // Directly use the message as it's already parsed
    } catch (error) {
      console.error('Failed to process WebSocket message in useRealTimeData:', error);
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

import { create } from 'zustand';
import {
  DashboardRealtimeUpdates,
  // Removed redundant interface definitions, now imported from types.ts
} from '../types'; // Import all necessary types from types.ts

interface MissionControlState {
  data: DashboardRealtimeUpdates | null;
  lastUpdated: string | null;
  setData: (newData: DashboardRealtimeUpdates) => void;
}

const useMissionControlStore = create<MissionControlState>((set) => ({
  data: null,
  lastUpdated: null,
  setData: (newData) => set({ data: newData, lastUpdated: newData.timestamp }),
}));

export default useMissionControlStore;

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.services.mission_control_service import mission_control_service
from Link_Profiler.api.schemas import DashboardRealtimeUpdates # Import the new schema

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

@mission_control_router.websocket("/ws/mission-control")
async def mission_control_websocket(websocket: WebSocket):
    """WebSocket endpoint streaming mission control updates."""
    await connection_manager.connect(websocket)
    try:
        while True:
            # Ensure mission_control_service is initialized
            if mission_control_service is None:
                logger.error("MissionControlService is not initialized. Cannot send updates.")
                await asyncio.sleep(5) # Wait before retrying
                continue

            updates: DashboardRealtimeUpdates = await mission_control_service.get_realtime_updates()
            await websocket.send_json(updates.model_dump_json()) # Use model_dump_json for Pydantic v2
            await asyncio.sleep(mission_control_service.websocket_refresh_rate_seconds)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Mission control websocket disconnected.")
    except Exception as e:
        logger.error(f"Mission control websocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.services.mission_control_service import mission_control_service # Import the global instance
from Link_Profiler.api.schemas import DashboardRealtimeUpdates # Import the new schema
import asyncio # Import asyncio

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

@mission_control_router.websocket("/ws/mission-control")
async def mission_control_websocket(websocket: WebSocket):
    """WebSocket endpoint streaming mission control updates."""
    # Check if mission_control_service is initialized and WebSocket is enabled
    if not mission_control_service or not mission_control_service.websocket_enabled:
        logger.warning("Mission Control WebSocket is disabled or service not initialized. Closing connection.")
        await websocket.close(code=1008) # Policy Violation
        return

    # Check for maximum connections
    if len(connection_manager.active_connections) >= mission_control_service.max_websocket_connections:
        logger.warning(f"Max WebSocket connections ({mission_control_service.max_websocket_connections}) reached. Rejecting new connection.")
        await websocket.close(code=1008) # Policy Violation
        return

    await connection_manager.connect(websocket)
    logger.info(f"Mission control websocket connected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(connection_manager.active_connections)}")
    try:
        while True:
            updates: DashboardRealtimeUpdates = await mission_control_service.get_realtime_updates()
            # Pydantic v2 models have .model_dump_json() for JSON string output
            await websocket.send_text(updates.model_dump_json()) 
            await asyncio.sleep(mission_control_service.dashboard_refresh_rate_seconds)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Mission control websocket disconnected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(connection_manager.active_connections)}")
    except Exception as e:
        logger.error(f"Mission control websocket error for {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)
        connection_manager.disconnect(websocket)

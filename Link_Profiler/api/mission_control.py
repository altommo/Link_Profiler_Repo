import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.services.mission_control_service import mission_control_service

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

@mission_control_router.websocket("/ws/mission-control")
async def mission_control_websocket(websocket: WebSocket):
    """WebSocket endpoint streaming mission control updates."""
    await connection_manager.connect(websocket)
    try:
        while True:
            updates = await mission_control_service.get_realtime_updates()
            await websocket.send_json(updates)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Mission control websocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)

import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Use the shared ConnectionManager instance
from Link_Profiler.utils.connection_manager import connection_manager

# Get module logger
logger = logging.getLogger(__name__)


websocket_router = APIRouter(tags=["WebSockets"])

@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates on job status and alerts."""
    await connection_manager.connect(websocket)
    # Notify the newly connected client
    await connection_manager.send_personal_message("connected", websocket)
    try:
        while True:
            # Echo any received message to all connected clients
            message = await websocket.receive_text()
            await connection_manager.broadcast(message)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(
            f"WebSocket error for {websocket.client.host}:{websocket.client.port}: {e}",
            exc_info=True,
        )
        connection_manager.disconnect(websocket)

# Removed duplicate /ws/mission-control endpoint - it's handled in mission_control.py

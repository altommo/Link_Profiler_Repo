import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Use the shared ConnectionManager instance
from Link_Profiler.utils.connection_manager import connection_manager

# Get module logger
logger = logging.getLogger(__name__)


websocket_router = APIRouter(tags=["WebSockets"])

@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates on job status and alerts.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive. Clients can send messages, but we don't expect them.
            # If a message is received, it can be processed or ignored.
            # A simple ping-pong or timeout mechanism could be added for robustness.
            await websocket.receive_text() # This will block until a message is received or connection closes
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)
        connection_manager.disconnect(websocket)

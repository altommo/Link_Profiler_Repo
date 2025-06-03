import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import logger, connection_manager
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy connection_manager for testing or if main.py is not fully initialized
    class DummyConnectionManager:
        async def connect(self, websocket): pass
        def disconnect(self, websocket): pass
    connection_manager = DummyConnectionManager()


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

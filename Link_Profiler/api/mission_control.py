import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.services.mission_control_service import mission_control_service # Import the global instance
from Link_Profiler.api.schemas import DashboardRealtimeUpdates # Import the new schema
import asyncio # Import asyncio
import json

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

@mission_control_router.get("/test")
async def test_mission_control():
    """Simple test endpoint to verify mission control router is working."""
    return {
        "status": "ok",
        "message": "Mission Control router is working",
        "service_available": mission_control_service is not None,
        "websocket_enabled": getattr(mission_control_service, 'websocket_enabled', False) if mission_control_service else False
    }

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

@mission_control_router.websocket("/ws/dashboard")
async def dashboard_websocket_alias(websocket: WebSocket):
    """Alias WebSocket endpoint for dashboard (legacy compatibility)."""
    logger.info(f"WebSocket connection attempt to /ws/dashboard from {websocket.client.host if websocket.client else 'unknown'}")
    
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted for /ws/dashboard")
        
        # Simple test - send a basic message first
        test_message = {
            "type": "connection_test",
            "message": "WebSocket connected successfully",
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send_text(json.dumps(test_message))
        logger.info("Sent test message to WebSocket")
        
        # Check if mission_control_service is available
        if not mission_control_service:
            logger.warning("Mission control service not available, sending error message")
            error_message = {
                "type": "error",
                "message": "Mission control service not initialized"
            }
            await websocket.send_text(json.dumps(error_message))
            await websocket.close(code=1011)
            return
        
        # Now try to redirect to the main mission control websocket handler
        await mission_control_websocket(websocket)
        
    except Exception as e:
        logger.error(f"Error in dashboard websocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass

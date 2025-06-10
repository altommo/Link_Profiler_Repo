import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.api.schemas import DashboardRealtimeUpdates
import asyncio
import json
from datetime import datetime
from starlette.websockets import WebSocketState

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

def get_mission_control_service():
    """Dynamically get the mission control service instance."""
    try:
        from Link_Profiler.services.mission_control_service import mission_control_service
        return mission_control_service
    except ImportError:
        logger.error("MissionControlService could not be imported. Is it initialized in main.py?")
        return None

@mission_control_router.post("/api/mission-control/token")
async def mission_control_login(request: Request):
    """Token endpoint for mission control dashboard."""
    client_info = f"{request.client.host}:{request.client.port}" if request.client else 'unknown client'
    logger.info(f"Mission control login attempt from {client_info}")
    try:
        content_type = request.headers.get("content-type", "")
        
        if "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            username = form_data.get("username")
            password = form_data.get("password")
        elif "application/json" in content_type:
            json_data = await request.json()
            username = json_data.get("username")
            password = json_data.get("password")
        else:
            username = "monitor_user" # Default for non-standard requests
            password = "accepted" # Default for non-standard requests
        
        logger.info(f"Mission control login attempt for user: {username}")
        
        from datetime import datetime, timedelta
        import jwt
        
        payload = {
            "sub": "monitor_user",
            "role": "admin", 
            "organization_id": None,
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        
        secret = "mission-control-secret-key" # This should ideally come from config_loader
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        logger.info(f"Mission control login successful for {username}. Token generated.")
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Error in mission_control_login: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Internal server error during login",
            "error": str(e)
        }

# REMOVED: This endpoint was causing confusion by hardcoding user info
# @mission_control_router.get("/api/mission-control/users/me")
# async def get_current_user():
#     """Get current user info - mission control dashboard compatibility."""
#     logger.info("Mission control /users/me endpoint accessed.")
#     try:
#         return {
#             "username": "monitor_user",
#             "role": "admin",
#             "organization_id": None,
#             "is_active": True,
#             "is_admin": True
#         }
#     except Exception as e:
#         logger.error(f"Error in get_current_user: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error fetching user info")

@mission_control_router.get("/api/mission-control/reset-connections")
async def reset_websocket_connections():
    """Reset WebSocket connections counter - for debugging."""
    logger.info("Resetting WebSocket connections.")
    try:
        initial_count = len(connection_manager.active_connections)
        # Disconnect all active connections gracefully
        for ws in list(connection_manager.active_connections):
            try:
                await ws.close(code=1000, reason="Admin reset")
            except Exception as e:
                logger.warning(f"Error closing WebSocket during reset: {e}")
        connection_manager.active_connections.clear()
        
        logger.info(f"Cleared {initial_count} stale connections. Current active: {len(connection_manager.active_connections)}")
        return {
            "success": True,
            "message": f"Cleared {initial_count} stale connections",
            "active_connections_before": initial_count,
            "active_connections_after": len(connection_manager.active_connections)
        }
    except Exception as e:
        logger.error(f"Error resetting WebSocket connections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset connections: {e}")

@mission_control_router.get("/api/mission-control/debug")
async def debug_mission_control_data():
    """Debug endpoint to see the exact data being sent via WebSocket."""
    logger.info("Debug endpoint /api/mission-control/debug accessed.")
    service = get_mission_control_service()
    if not service:
        logger.error("Mission control service not available for debug endpoint.")
        raise HTTPException(status_code=503, detail="Mission control service not available")
    
    try:
        updates = await service.get_realtime_updates()
        
        try:
            json_data = updates.model_dump_json()
            logger.info("Debug data serialized successfully.")
            return {
                "success": True,
                "json_length": len(json_data),
                "json_preview": json_data[:500],
                "data_structure": updates.model_dump()
            }
        except Exception as e:
            logger.error(f"Error serializing debug data: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error serializing debug data: {e}")
    except Exception as e:
        logger.error(f"Failed to get updates for debug endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get updates: {e}")

@mission_control_router.get("/api/mission-control/websocket-status")
async def websocket_status():
    """Check WebSocket configuration status."""
    logger.info("WebSocket status endpoint accessed.")
    service = get_mission_control_service()
    if not service:
        logger.error("Mission control service not available for WebSocket status.")
        raise HTTPException(status_code=503, detail="Mission control service not available")
    
    return {
        "websocket_enabled": service.websocket_enabled,
        "max_connections": service.max_websocket_connections,
        "refresh_rate_ms": service.dashboard_refresh_rate_seconds * 1000,
        "cache_ttl": service.cache_ttl_seconds,
        "active_connections": len(connection_manager.active_connections)
    }

@mission_control_router.websocket("/ws/mission-control")
async def mission_control_websocket(websocket: WebSocket):
    """WebSocket endpoint streaming mission control updates."""
    client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else 'unknown'
    logger.info(f"WebSocket connection attempt to /ws/mission-control from {client_info}")
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for {client_info}")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection from {client_info}: {e}", exc_info=True)
        return
    
    mission_control_service = get_mission_control_service()
    
    logger.debug(f"Mission control service check for {client_info}: service={mission_control_service}, service_type={type(mission_control_service)}")
    if mission_control_service:
        logger.debug(f"Mission control service websocket_enabled: {getattr(mission_control_service, 'websocket_enabled', 'ATTRIBUTE_NOT_FOUND')}")
        logger.debug(f"Mission control service max_connections: {getattr(mission_control_service, 'max_websocket_connections', 'ATTRIBUTE_NOT_FOUND')}")
    
    if not mission_control_service:
        logger.error(f"Mission Control service is None for {client_info}! Service not initialized properly.")
        await websocket.close(code=1011, reason="Service not initialized")
        return
        
    if not hasattr(mission_control_service, 'websocket_enabled') or not mission_control_service.websocket_enabled:
        logger.warning(f"Mission Control WebSocket is disabled for {client_info}. websocket_enabled={getattr(mission_control_service, 'websocket_enabled', 'N/A')}")
        error_message = {
            "type": "error",
            "message": "WebSocket is disabled by configuration",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))
        await websocket.close(code=1011, reason="WebSocket disabled")
        return

    active_connections_count = len(connection_manager.active_connections)
    logger.info(f"Current active WebSocket connections: {active_connections_count}/{mission_control_service.max_websocket_connections} for {client_info}")
    
    if active_connections_count >= mission_control_service.max_websocket_connections:
        logger.warning(f"Max WebSocket connections ({mission_control_service.max_websocket_connections}) reached. Rejecting new connection from {client_info}.")
        error_message = {
            "type": "error",
            "message": "Maximum WebSocket connections reached",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))
        await websocket.close(code=1013, reason="Max connections reached")
        return

    # Add to connection manager
    connection_manager.connect(websocket)
    logger.info(f"Mission control websocket connected: {client_info}. Total active connections: {len(connection_manager.active_connections)}")
    
    try:
        # Send connection confirmation
        connection_message = {
            "type": "connection_established",
            "message": "WebSocket connected successfully",
            "timestamp": datetime.now().isoformat()
        }
        try:
            logger.debug(f"Attempting to send connection confirmation to {client_info}. Current state: {websocket.client_state.name}")
            await websocket.send_text(json.dumps(connection_message))
            logger.info(f"Sent connection confirmation to {client_info}. State after send: {websocket.client_state.name}")
        except WebSocketDisconnect:
            logger.warning(f"WebSocket for {client_info} disconnected during connection confirmation send. Exiting WebSocket handler.")
            return # Exit early if initial send fails
        except Exception as e:
            logger.error(f"Error sending connection confirmation to {client_info}: {e}", exc_info=True)
            return # Exit early on other errors
        
        # Start the real-time data loop
        last_full_data_sent_time = datetime.now()
        last_heartbeat_sent_time = datetime.now()
        HEARTBEAT_INTERVAL_SECONDS = 5 # Define a heartbeat interval, e.g., every 5 seconds
        
        while True:
            try:
                current_time = datetime.now()
                refresh_rate_seconds = mission_control_service.dashboard_refresh_rate_seconds

                # Check if it's time to send a full dashboard update
                if (current_time - last_full_data_sent_time).total_seconds() >= refresh_rate_seconds:
                    logger.debug(f"Fetching dashboard data for {client_info} (full refresh)...")
                    dashboard_updates = await mission_control_service.get_realtime_updates()
                    dashboard_json = dashboard_updates.model_dump_json()
                    
                    logger.debug(f"Attempting to send dashboard update to {client_info}: {len(dashboard_json)} characters. Current state: {websocket.client_state.name}")
                    try:
                        await websocket.send_text(dashboard_json)
                        logger.debug(f"Successfully sent dashboard data to {client_info}. State after send: {websocket.client_state.name}")
                        last_full_data_sent_time = current_time # Reset timer for full data
                        last_heartbeat_sent_time = current_time # Also reset heartbeat timer, as full data acts as heartbeat
                    except WebSocketDisconnect:
                        logger.info(f"WebSocket for {client_info} disconnected during dashboard data send. Breaking loop.")
                        break # Break on disconnect during send
                    except Exception as e:
                        logger.error(f"Error sending dashboard data to {client_info}: {e}", exc_info=True)
                        break # Break on other errors during send
                
                # If not time for full data, check if it's time for a heartbeat
                elif (current_time - last_heartbeat_sent_time).total_seconds() >= HEARTBEAT_INTERVAL_SECONDS:
                    heartbeat_message = {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    }
                    logger.debug(f"Attempting to send heartbeat to {client_info}. Current state: {websocket.client_state.name}")
                    try:
                        await websocket.send_text(json.dumps(heartbeat_message))
                        logger.debug(f"Sent heartbeat to {client_info}. State after send: {websocket.client_state.name}")
                        last_heartbeat_sent_time = current_time # Reset timer for heartbeat
                    except WebSocketDisconnect:
                        logger.info(f"WebSocket for {client_info} disconnected during heartbeat send. Breaking loop.")
                        break # Break on disconnect during send
                    except Exception as e:
                        logger.error(f"Error sending heartbeat to {client_info}: {e}", exc_info=True)
                        break # Break on other errors during send
                
                # Yield control to the event loop briefly
                await asyncio.sleep(0.01) # Small sleep to allow other tasks to run and state to update
                
                # Check if WebSocket is still connected after potential send/sleep
                if websocket.client_state != WebSocketState.CONNECTED:
                    logger.info(f"WebSocket for {client_info} no longer connected (state: {websocket.client_state.name}), breaking loop after check.")
                    break
                    
            except WebSocketDisconnect:
                # This catches disconnects that happen during the asyncio.sleep or other awaitables
                logger.info(f"WebSocket for {client_info} disconnected during data loop (caught by outer exception).")
                break
            except Exception as e:
                logger.error(f"Unhandled error in dashboard update loop for {client_info}: {e}", exc_info=True)
                # Attempt to send error message if still connected
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        error_message = {
                            "type": "error",
                            "message": f"Dashboard update error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send_text(json.dumps(error_message))
                except WebSocketDisconnect:
                    logger.error(f"Could not send error message to {client_info}, WebSocket already closed.")
                except Exception as send_error:
                    logger.error(f"Unexpected error sending error message to {client_info}: {send_error}", exc_info=True)
                break # Break on any other exception to prevent infinite loops
            
    except WebSocketDisconnect:
        logger.info(f"Mission control websocket disconnected gracefully for {client_info}.")
    except Exception as e:
        logger.error(f"Mission control websocket error for {client_info}: {e}", exc_info=True)
    finally:
        # Ensure connection is removed from manager on exit
        connection_manager.disconnect(websocket)
        logger.info(f"Mission control websocket cleanup complete for {client_info}. Total active connections: {len(connection_manager.active_connections)}")

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from Link_Profiler.utils.connection_manager import connection_manager
from Link_Profiler.api.schemas import DashboardRealtimeUpdates # Import the new schema
import asyncio # Import asyncio
import json
from datetime import datetime

mission_control_router = APIRouter(tags=["Mission Control"])
logger = logging.getLogger(__name__)

def get_mission_control_service():
    """Dynamically get the mission control service instance."""
    try:
        from Link_Profiler.services.mission_control_service import mission_control_service
        return mission_control_service
    except ImportError:
        return None

@mission_control_router.post("/api/mission-control/token")
async def mission_control_login(request: Request):
    """Token endpoint for mission control dashboard."""
    try:
        # For mission control, we'll accept any login and return a token
        # Get the request body to handle form data
        content_type = request.headers.get("content-type", "")
        
        if "application/x-www-form-urlencoded" in content_type:
            # Handle form data (like from login form)
            form_data = await request.form()
            username = form_data.get("username")
            password = form_data.get("password")
        elif "application/json" in content_type:
            # Handle JSON data
            json_data = await request.json()
            username = json_data.get("username")
            password = json_data.get("password")
        else:
            # Default case - accept any request
            username = "monitor_user"
            password = "accepted"
        
        logger.info(f"Mission control login attempt for user: {username}")
        
        # Create a simple JWT token
        from datetime import datetime, timedelta
        import jwt
        
        payload = {
            "sub": "monitor_user",
            "role": "admin", 
            "organization_id": None,
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        
        # Use a simple secret - in production use proper secret management
        secret = "mission-control-secret-key"
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    except Exception as e:
        logger.error(f"Error in mission_control_login: {e}")
        # Still return a token for mission control
        return {
            "access_token": "dummy-token-for-mission-control",
            "token_type": "bearer"
        }

@mission_control_router.get("/api/mission-control/users/me")
async def get_current_user():
    """Get current user info - mission control dashboard compatibility."""
    try:
        # Simple hardcoded response for mission control dashboard
        return {
            "username": "monitor_user",
            "role": "admin",
            "organization_id": None,
            "is_active": True,
            "is_admin": True
        }
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        return {
            "error": "Failed to get user info",
            "username": "monitor_user",
            "role": "admin",
            "organization_id": None,
            "is_active": True,
            "is_admin": True
        }

@mission_control_router.get("/api/mission-control/reset-connections")
async def reset_websocket_connections():
    """Reset WebSocket connections counter - for debugging."""
    try:
        # Clear stale connections
        initial_count = len(connection_manager.active_connections)
        connection_manager.active_connections.clear()
        
        return {
            "success": True,
            "message": f"Cleared {initial_count} stale connections",
            "active_connections_before": initial_count,
            "active_connections_after": len(connection_manager.active_connections)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@mission_control_router.get("/api/mission-control/debug")
async def debug_mission_control_data():
    """Debug endpoint to see the exact data being sent via WebSocket."""
    service = get_mission_control_service()
    if not service:
        return {"error": "Mission control service not available"}
    
    try:
        updates = await service.get_realtime_updates()
        
        # Try to serialize to JSON
        try:
            json_data = updates.model_dump_json()
            return {
                "success": True,
                "json_length": len(json_data),
                "json_preview": json_data[:500],
                "data_structure": updates.model_dump()
            }
        except Exception as e:
            return {
                "success": False,
                "serialization_error": str(e),
                "error_type": type(e).__name__,
                "raw_object": str(updates)
            }
    except Exception as e:
        return {
            "error": f"Failed to get updates: {e}",
            "error_type": type(e).__name__
        }

@mission_control_router.get("/api/mission-control/test")
async def test_mission_control_api():
    """API test endpoint to verify mission control router is working."""
    service = get_mission_control_service()
    return {
        "status": "ok",
        "message": "Mission Control API is working",
        "service_available": service is not None,
        "websocket_enabled": getattr(service, 'websocket_enabled', False) if service else False
    }

@mission_control_router.get("/api/mission-control/websocket-status")
async def websocket_status():
    """Check WebSocket configuration status."""
    service = get_mission_control_service()
    if not service:
        return {
            "websocket_enabled": False,
            "error": "Mission control service not available"
        }
    
    return {
        "websocket_enabled": service.websocket_enabled,
        "max_connections": service.max_websocket_connections,
        "refresh_rate_ms": service.dashboard_refresh_rate_seconds * 1000,
        "cache_ttl": service.cache_ttl_seconds,
        "active_connections": len(connection_manager.active_connections)
    }

@mission_control_router.get("/test")
async def test_mission_control():
    """Simple test endpoint to verify mission control router is working."""
    service = get_mission_control_service()
    return {
        "status": "ok",
        "message": "Mission Control router is working",
        "service_available": service is not None,
        "websocket_enabled": getattr(service, 'websocket_enabled', False) if service else False
    }

@mission_control_router.websocket("/ws/mission-control")
async def mission_control_websocket(websocket: WebSocket):
    """WebSocket endpoint streaming mission control updates."""
    logger.info(f"WebSocket connection attempt to /ws/mission-control from {websocket.client.host if websocket.client else 'unknown'}")
    
    # Accept the WebSocket connection first
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted successfully")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection: {e}")
        return
    
    # Get the mission control service dynamically
    mission_control_service = get_mission_control_service()
    
    # Debug the mission control service state
    logger.info(f"Mission control service check: service={mission_control_service}, service_type={type(mission_control_service)}")
    if mission_control_service:
        logger.info(f"Mission control service websocket_enabled: {getattr(mission_control_service, 'websocket_enabled', 'ATTRIBUTE_NOT_FOUND')}")
        logger.info(f"Mission control service max_connections: {getattr(mission_control_service, 'max_websocket_connections', 'ATTRIBUTE_NOT_FOUND')}")
    
    # Check if mission_control_service is initialized and WebSocket is enabled
    if not mission_control_service:
        logger.error("Mission Control service is None! Service not initialized properly.")
        await websocket.close(code=1011) # Internal Error
        return
        
    if not hasattr(mission_control_service, 'websocket_enabled'):
        logger.error("Mission Control service missing websocket_enabled attribute!")
        await websocket.close(code=1011) # Internal Error
        return
        
    if not mission_control_service.websocket_enabled:
        logger.warning(f"Mission Control WebSocket is disabled. websocket_enabled={mission_control_service.websocket_enabled}")
        error_message = {
            "type": "error",
            "message": "WebSocket is disabled by configuration",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))
        await websocket.close(code=1011) # Internal Error
        return

    # Check for maximum connections
    active_connections_count = len(connection_manager.active_connections)
    logger.info(f"Current active WebSocket connections: {active_connections_count}/{mission_control_service.max_websocket_connections}")
    
    if active_connections_count >= mission_control_service.max_websocket_connections:
        logger.warning(f"Max WebSocket connections ({mission_control_service.max_websocket_connections}) reached. Rejecting new connection.")
        error_message = {
            "type": "error",
            "message": "Maximum WebSocket connections reached",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))
        await websocket.close(code=1013) # Try Again Later
        return

    # Add to connection manager
    connection_manager.active_connections.append(websocket)
    logger.info(f"Mission control websocket connected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(connection_manager.active_connections)}")
    
    try:
        # Send connection confirmation
        connection_message = {
            "type": "connection_established",
            "message": "WebSocket connected successfully",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(connection_message))
        logger.info("Sent connection confirmation")
        
        # Start the real-time data loop
        while True:
            try:
                # Check if WebSocket is still connected before sending
                if websocket.client_state.name != 'CONNECTED':
                    logger.info("WebSocket no longer connected, breaking loop")
                    break
                    
                logger.debug("Fetching dashboard data...")
                
                # Get real dashboard data from mission control service
                dashboard_updates = await mission_control_service.get_realtime_updates()
                
                # Convert to JSON-serializable format
                dashboard_json = dashboard_updates.model_dump_json()
                
                # Debug: Log what we're about to send
                logger.debug(f"Sending dashboard update: {len(dashboard_json)} characters")
                logger.debug(f"Dashboard JSON type: {type(dashboard_json)}")
                logger.debug(f"Dashboard JSON preview: {dashboard_json[:100]}...")
                
                # Ensure we're sending a string, not an object
                if isinstance(dashboard_json, str):
                    await websocket.send_text(dashboard_json)
                    logger.debug("Sent JSON string successfully")
                else:
                    # Fallback: convert to JSON string
                    json_string = json.dumps(dashboard_json)
                    logger.debug(f"Converted to JSON string: {type(json_string)}")
                    await websocket.send_text(json_string)
                logger.debug("Successfully sent dashboard data")
                
                # Wait before sending next update (use configured refresh rate)
                refresh_rate_ms = mission_control_service.dashboard_refresh_rate_seconds * 1000
                await asyncio.sleep(refresh_rate_ms / 1000)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected during data loop")
                break
            except Exception as e:
                logger.error(f"Error in dashboard update loop: {e}")
                # Check if we can still send error messages
                try:
                    if websocket.client_state.name == 'CONNECTED':
                        error_message = {
                            "type": "error",
                            "message": f"Dashboard update error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send_text(json.dumps(error_message))
                except:
                    logger.error("Could not send error message, WebSocket likely closed")
                    break
                await asyncio.sleep(5)  # Wait before retrying
            
    except WebSocketDisconnect:
        # Remove from connection manager
        if websocket in connection_manager.active_connections:
            connection_manager.active_connections.remove(websocket)
        logger.info(f"Mission control websocket disconnected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(connection_manager.active_connections)}")
    except Exception as e:
        logger.error(f"Mission control websocket error for {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)
        # Remove from connection manager on any error
        if websocket in connection_manager.active_connections:
            connection_manager.active_connections.remove(websocket)
        try:
            if hasattr(websocket, 'client_state') and websocket.client_state.name != 'DISCONNECTED':
                await websocket.close(code=1011)
        except:
            pass  # Ignore errors when closing

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
        
        # Get the mission control service dynamically
        mission_control_service = get_mission_control_service()
        
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

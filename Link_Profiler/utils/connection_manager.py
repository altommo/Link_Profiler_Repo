"""
Connection Manager - Manages WebSocket connections for real-time updates.
File: Link_Profiler/utils/connection_manager.py
"""

import logging
import json
from typing import List, Dict, Any, Union
from fastapi import WebSocket
from starlette.websockets import WebSocketState # Import WebSocketState

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages active WebSocket connections, allowing messages to be sent to individual
    clients or broadcast to all connected clients.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__ + ".ConnectionManager")
        self.logger.info("ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket):
        """Adds a new WebSocket connection to the manager."""
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection from the manager."""
        try:
            self.active_connections.remove(websocket)
            self.logger.info(f"WebSocket disconnected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")
        except ValueError:
            self.logger.warning(f"Attempted to disconnect non-existent WebSocket: {websocket.client.host}:{websocket.client.port}")

    async def send_personal_message(self, message: Union[str, Dict[str, Any]], websocket: WebSocket):
        """Sends a message to a specific WebSocket client."""
        # Check if connection is still active before sending
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                if isinstance(message, dict):
                    await websocket.send_json(message)
                else:
                    await websocket.send_text(message)
                self.logger.debug(f"Sent message to {websocket.client.host}:{websocket.client.port}")
            except Exception as e:
                self.logger.error(f"Failed to send message to {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)
                await self.disconnect(websocket) # Disconnect if sending fails
        else:
            self.logger.warning(f"Attempted to send message to disconnected WebSocket: {websocket.client.host}:{websocket.client.port}")
            await self.disconnect(websocket) # Ensure it's removed if state is not connected

    async def broadcast(self, message: Union[str, Dict[str, Any]]):
        """Broadcasts a message to all active WebSocket connections."""
        disconnected_websockets = []
        # Create a copy of the list to iterate over, as it might be modified during iteration
        for connection in list(self.active_connections): 
            if connection.client_state == WebSocketState.CONNECTED: # Check if connection is still active
                try:
                    if isinstance(message, dict):
                        await connection.send_json(message)
                    else:
                        await connection.send_text(message)
                except Exception as e:
                    self.logger.error(f"Failed to broadcast message to {connection.client.host}:{connection.client.port}: {e}", exc_info=True)
                    disconnected_websockets.append(connection) # Mark for removal
            else:
                self.logger.warning(f"Attempted to broadcast to disconnected WebSocket: {connection.client.host}:{connection.client.port}")
                disconnected_websockets.append(connection) # Mark for removal
        
        # Clean up disconnected websockets
        for ws in disconnected_websockets:
            await self.disconnect(ws) # Use disconnect method to ensure proper logging/removal

# Create a singleton instance
connection_manager = ConnectionManager()

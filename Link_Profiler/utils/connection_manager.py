"""
Connection Manager - Manages WebSocket connections for real-time updates.
File: Link_Profiler/utils/connection_manager.py
"""

import logging
import json
from typing import List, Dict, Any, Union
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages active WebSocket connections, allowing messages to be sent to individual
    clients or broadcast to all connected clients.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__ + ".ConnectionManager")

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection and adds it to the active list."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Removes a disconnected WebSocket from the active list."""
        self.active_connections.remove(websocket)
        self.logger.info(f"WebSocket disconnected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Sends a text message to a specific WebSocket client."""
        try:
            await websocket.send_text(message)
        except WebSocketDisconnect:
            self.logger.warning(f"Attempted to send message to disconnected WebSocket: {websocket.client.host}:{websocket.client.port}")
            self.disconnect(websocket)
        except Exception as e:
            self.logger.error(f"Error sending personal message to WebSocket {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)

    async def broadcast(self, message: Union[str, Dict[str, Any]]):
        """Broadcasts a message to all active WebSocket connections."""
        if isinstance(message, (dict, list)):
            message_str = json.dumps(message)
        else:
            message_str = str(message)
        disconnected_websockets = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except WebSocketDisconnect:
                disconnected_websockets.append(connection)
                self.logger.warning(f"WebSocket disconnected during broadcast: {connection.client.host}:{connection.client.port}")
            except Exception as e:
                self.logger.error(f"Error sending message to WebSocket {connection.client.host}:{connection.client.port}: {e}", exc_info=True)
                disconnected_websockets.append(connection)
        
        # Clean up disconnected websockets after iterating
        for ws in disconnected_websockets:
            if ws in self.active_connections:
                self.active_connections.remove(ws)
        self.logger.debug(
            f"Broadcasted message to {len(self.active_connections)} active connections. Message type: {message.get('type') if isinstance(message, dict) else 'text'}"
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        for ws in list(self.active_connections):
            try:
                await ws.close()
            except Exception:
                pass
            self.disconnect(ws)

# Global instance of ConnectionManager
connection_manager = ConnectionManager()

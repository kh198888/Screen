"""
WebSocket server module for handling client connections.
Manages real-time communication with monitoring agents.
"""

import asyncio
import json
import time
import os
import struct
from datetime import datetime
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for monitoring clients.
    """
    
    def __init__(self):
        """Initialize connection manager."""
        # Active connections: computer_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        
        # Dashboard connections: Set of WebSocket objects
        self.dashboard_connections: Set[WebSocket] = set()
        
        # Computer info cache: computer_id -> device_info
        self.computer_info: Dict[int, Dict] = {}
        
        # Latest frame cache: computer_id -> frame bytes
        self.frame_cache: Dict[int, bytes] = {}
        
        # Stats cache: computer_id -> stats
        self.stats_cache: Dict[int, Dict] = {}
    
    async def connect_client(self, websocket: WebSocket, computer_id: int):
        """
        Connect a monitoring client.
        
        Args:
            websocket: WebSocket connection
            computer_id: Computer ID
        """
        await websocket.accept()
        self.active_connections[computer_id] = websocket
        logger.info(f"Client {computer_id} connected. Total clients: {len(self.active_connections)}")
    
    async def connect_dashboard(self, websocket: WebSocket):
        """
        Connect a dashboard viewer.
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.dashboard_connections.add(websocket)
        logger.info(f"Dashboard connected. Total dashboards: {len(self.dashboard_connections)}")
    
    def disconnect_client(self, computer_id: int, websocket: Optional[WebSocket] = None):
        """
        Disconnect a monitoring client.
        
        Args:
            computer_id: Computer ID
        """
        # A reconnect can replace the socket for the same computer. Do not
        # remove that newer connection when the older socket closes.
        if (computer_id in self.active_connections and
                (websocket is None or self.active_connections[computer_id] is websocket)):
            del self.active_connections[computer_id]
            logger.info(f"Client {computer_id} disconnected. Total clients: {len(self.active_connections)}")
    
    def disconnect_dashboard(self, websocket: WebSocket):
        """
        Disconnect a dashboard viewer.
        
        Args:
            websocket: WebSocket connection
        """
        if websocket in self.dashboard_connections:
            self.dashboard_connections.remove(websocket)
            logger.info(f"Dashboard disconnected. Total dashboards: {len(self.dashboard_connections)}")
    
    def is_client_connected(self, computer_id: int) -> bool:
        """
        Check if a client is connected.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            True if connected
        """
        return computer_id in self.active_connections
    
    def get_client_websocket(self, computer_id: int) -> Optional[WebSocket]:
        """
        Get WebSocket for a client.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            WebSocket or None
        """
        return self.active_connections.get(computer_id)
    
    def update_computer_info(self, computer_id: int, device_info: Dict):
        """
        Update cached computer information.
        
        Args:
            computer_id: Computer ID
            device_info: Device information dictionary
        """
        self.computer_info[computer_id] = device_info
    
    def get_computer_info(self, computer_id: int) -> Optional[Dict]:
        """
        Get cached computer information.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            Device info or None
        """
        return self.computer_info.get(computer_id)
    
    def update_frame_cache(self, computer_id: int, frame: bytes):
        """
        Update cached frame for a computer.
        
        Args:
            computer_id: Computer ID
            frame: JPEG frame bytes
        """
        self.frame_cache[computer_id] = frame
    
    def get_frame(self, computer_id: int) -> Optional[bytes]:
        """
        Get cached frame for a computer.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            Frame bytes or None
        """
        return self.frame_cache.get(computer_id)
    
    def update_stats(self, computer_id: int, stats: Dict):
        """
        Update cached stats for a computer.
        
        Args:
            computer_id: Computer ID
            stats: Stats dictionary
        """
        self.stats_cache[computer_id] = stats
    
    def get_stats(self, computer_id: int) -> Optional[Dict]:
        """
        Get cached stats for a computer.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            Stats dictionary or None
        """
        return self.stats_cache.get(computer_id)
    
    async def broadcast_to_dashboards(self, message: dict):
        """
        Broadcast message to all connected dashboards.
        
        Args:
            message: Message dictionary to broadcast
        """
        if not self.dashboard_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for dashboard in self.dashboard_connections:
            try:
                if dashboard.client_state == WebSocketState.CONNECTED:
                    await dashboard.send_text(message_str)
            except Exception as e:
                logger.error(f"Error sending to dashboard: {e}")
                disconnected.add(dashboard)
        
        # Remove disconnected dashboards
        for dashboard in disconnected:
            self.disconnect_dashboard(dashboard)
    
    async def send_frame_to_dashboards(self, computer_id: int, frame: bytes):
        """
        Send frame to all connected dashboards as binary data with metadata.
        
        Args:
            computer_id: Computer ID
            frame: JPEG frame bytes
        """
        if not self.dashboard_connections:
            return
        
        disconnected = set()
        
        payload = self._frame_payload(computer_id, frame)
        
        for dashboard in self.dashboard_connections:
            try:
                if dashboard.client_state == WebSocketState.CONNECTED:
                    await dashboard.send_bytes(payload)
            except Exception as e:
                logger.error(f"Error sending frame to dashboard: {e}")
                disconnected.add(dashboard)
        
        # Remove disconnected dashboards
        for dashboard in disconnected:
            self.disconnect_dashboard(dashboard)

    def _frame_payload(self, computer_id: int, frame: bytes) -> bytes:
        """Build the binary frame format understood by the dashboard."""
        computer_info = self.get_computer_info(computer_id)
        width = computer_info.get("resolution_width", 1920) if computer_info else 1920
        height = computer_info.get("resolution_height", 1080) if computer_info else 1080
        timestamp = int(time.time() * 1000)
        header = struct.pack(">IIIQ", computer_id, width, height, timestamp)
        return header + frame

    async def send_cached_frame(self, websocket: WebSocket, computer_id: int, frame: bytes):
        """Send a cached frame using the same protocol as live frames."""
        await websocket.send_bytes(self._frame_payload(computer_id, frame))
    
    async def send_command_to_client(self, computer_id: int, command: str, **kwargs):
        """
        Send command to a specific client.
        
        Args:
            computer_id: Computer ID
            command: Command string
            **kwargs: Additional command parameters
        """
        websocket = self.get_client_websocket(computer_id)
        if websocket and websocket.client_state == WebSocketState.CONNECTED:
            try:
                message = {
                    "type": "command",
                    "command": command,
                    **kwargs
                }
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending command to client {computer_id}: {e}")
    
    def get_connected_computers(self) -> list:
        """
        Get list of connected computer IDs.
        
        Returns:
            List of computer IDs
        """
        return list(self.active_connections.keys())
    
    def get_connection_count(self) -> Dict[str, int]:
        """
        Get connection counts.
        
        Returns:
            Dictionary with client and dashboard counts
        """
        return {
            "clients": len(self.active_connections),
            "dashboards": len(self.dashboard_connections)
        }


# Global connection manager instance
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """
    Get or create global connection manager instance.
    
    Returns:
        ConnectionManager instance
    """
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


async def handle_client_websocket(
    websocket: WebSocket,
    computer_id: int,
    database
):
    """
    Handle WebSocket connection from a monitoring client.
    
    Args:
        websocket: WebSocket connection
        computer_id: Computer ID
        database: Database instance
    """
    manager = get_connection_manager()
    await manager.connect_client(websocket, computer_id)
    
    # Update computer online status
    database.set_computer_online(computer_id, online=True)
    
    try:
        while True:
            # Receive message from client
            message = await websocket.receive()
            
            if "text" in message:
                # Handle text messages (JSON)
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")
                    
                    if msg_type == "device_info":
                        # Update device info
                        device_info = data.get("data", {})
                        # The WebSocket query parameter is the authoritative
                        # identity for this connection.
                        device_info["mac_address"] = database.get_computer(computer_id)["mac_address"]
                        manager.update_computer_info(computer_id, device_info)
                        database.upsert_computer(device_info)
                        
                        # Broadcast to dashboards
                        await manager.broadcast_to_dashboards({
                            "type": "computer_updated",
                            "computer_id": computer_id,
                            "data": device_info
                        })
                    
                    elif msg_type == "heartbeat":
                        # Update last seen
                        database.set_computer_online(computer_id, online=True)
                        
                        # Broadcast to dashboards
                        await manager.broadcast_to_dashboards({
                            "type": "heartbeat",
                            "computer_id": computer_id,
                            "timestamp": data.get("timestamp")
                        })
                    
                    elif msg_type == "keyboard_event":
                        # Handle single keyboard event
                        event_data = data.get("data", {})
                        database.add_keyboard_event(computer_id, event_data)
                        
                        # Broadcast to dashboards
                        await manager.broadcast_to_dashboards({
                            "type": "keyboard_event",
                            "computer_id": computer_id,
                            "data": event_data
                        })
                    
                    elif msg_type == "keyboard_events_batch":
                        # Handle batch of keyboard events
                        events = data.get("data", [])
                        if events:
                            database.add_keyboard_events_batch(computer_id, events)
                            
                            # Broadcast to dashboards
                            for event in events:
                                await manager.broadcast_to_dashboards({
                                    "type": "keyboard_event",
                                    "computer_id": computer_id,
                                    "data": event
                                })
                    
                    elif msg_type == "stats":
                        # Update stats
                        stats = data.get("data", {})
                        manager.update_stats(computer_id, stats)
                        
                        # Broadcast to dashboards
                        await manager.broadcast_to_dashboards({
                            "type": "stats",
                            "computer_id": computer_id,
                            "data": stats
                        })
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
            
            elif "bytes" in message:
                # Handle binary messages (screen frames)
                frame_data = message["bytes"]
                
                # Update frame cache
                manager.update_frame_cache(computer_id, frame_data)
                
                # Broadcast to dashboards
                await manager.send_frame_to_dashboards(computer_id, frame_data)
    
    except WebSocketDisconnect:
        logger.info(f"Client {computer_id} disconnected normally")
    except Exception as e:
        logger.error(f"Error handling client websocket: {e}")
    finally:
        # Cleanup
        # Only the socket currently registered for this computer may mark it
        # offline; an older reconnecting socket must not evict the new one.
        if manager.get_client_websocket(computer_id) is websocket:
            manager.disconnect_client(computer_id, websocket)
            database.set_computer_online(computer_id, online=False)


async def handle_dashboard_websocket(websocket: WebSocket, computer_id: Optional[int] = None):
    """
    Handle WebSocket connection from a dashboard viewer.
    
    Args:
        websocket: WebSocket connection
        computer_id: Optional computer ID to monitor (None for all)
    """
    manager = get_connection_manager()
    await manager.connect_dashboard(websocket)
    
    try:
        while True:
            # Receive commands from dashboard
            message = await websocket.receive()
            
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")
                    
                    if msg_type == "command":
                        # Forward command to specific client
                        target_id = data.get("computer_id")
                        command = data.get("command")
                        params = data.get("params", {})
                        
                        if target_id and command:
                            await manager.send_command_to_client(target_id, command, **params)
                    
                    elif msg_type == "subscribe":
                        # Subscribe to specific computer
                        target_id = data.get("computer_id")
                        if target_id:
                            # Send latest frame if available
                            frame = manager.get_frame(target_id)
                            if frame:
                                await manager.send_cached_frame(websocket, target_id, frame)
                            
                            # Send latest stats
                            stats = manager.get_stats(target_id)
                            if stats:
                                await websocket.send_text(json.dumps({
                                    "type": "stats",
                                    "computer_id": target_id,
                                    "data": stats
                                }))
                
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
    
    except WebSocketDisconnect:
        logger.info("Dashboard disconnected normally")
    except Exception as e:
        logger.error(f"Error handling dashboard websocket: {e}")
    finally:
        manager.disconnect_dashboard(websocket)

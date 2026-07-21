"""
Screen capture module using MSS for high-performance screen monitoring.
Optimized for low CPU usage and minimal bandwidth consumption.
"""

import mss
import numpy as np
import cv2
import io
import threading
import queue
import time
import hashlib
from typing import Optional, Tuple
import psutil


class ScreenCapture:
    """
    High-performance screen capture using MSS with delta frame optimization.
    """
    
    def __init__(
        self,
        target_fps: int = 10,
        jpeg_quality: int = 50,
        max_bandwidth: int = 2_000_000,  # 2MB/sec
        max_cpu_percent: float = 8.0
    ):
        """
        Initialize screen capture.
        
        Args:
            target_fps: Target frames per second (5-10 recommended)
            jpeg_quality: JPEG compression quality (45-60)
            max_bandwidth: Maximum bandwidth in bytes per second
            max_cpu_percent: Maximum allowed CPU usage percentage
        """
        self.target_fps = target_fps
        self.jpeg_quality = jpeg_quality
        self.max_bandwidth = max_bandwidth
        self.max_cpu_percent = max_cpu_percent
        
        # MSS capture instance
        self.sct = mss.mss()
        
        # Get primary monitor
        self.monitor = self.sct.monitors[1]  # Primary monitor
        self.width = self.monitor["width"]
        self.height = self.monitor["height"]
        
        # Frame queue for thread-safe communication
        self.frame_queue = queue.Queue(maxsize=30)
        
        # Previous frame hash for delta detection
        self.previous_hash = None
        
        # Frame counter for periodic forced sends
        self.frame_counter = 0
        
        # Threading
        self.running = False
        self.capture_thread = None
        
        # Performance monitoring
        self.current_fps = 0
        self.frame_count = 0
        self.last_fps_update = time.time()
        self.bandwidth_usage = 0
        self.last_bandwidth_check = time.time()
        self.bandwidth_accumulator = 0
        
        # Dynamic FPS adjustment
        self.adaptive_fps = target_fps
        self.cpu_history = []
        
    def get_resolution(self) -> Tuple[int, int]:
        """Get current screen resolution."""
        return self.width, self.height
    
    def capture_frame(self) -> Optional[bytes]:
        """
        Capture a single frame and compress to JPEG.
        
        Returns:
            JPEG bytes or None if capture failed
        """
        try:
            # Capture screen using MSS
            screenshot = self.sct.grab(self.monitor)
            
            # Convert to numpy array
            frame = np.array(screenshot)
            
            # Remove alpha channel if present (BGRA -> BGR)
            if frame.shape[2] == 4:
                frame = frame[:, :, :3]
            
            # Calculate frame hash for duplicate detection
            frame_hash = hashlib.md5(frame.tobytes()).hexdigest()
            
            # Skip if duplicate, but force send every 30 frames (3 seconds at 10 FPS)
            self.frame_counter += 1
            if frame_hash == self.previous_hash and self.frame_counter % 30 != 0:
                return None
            
            self.previous_hash = frame_hash
            
            # Compress to JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            _, jpeg_bytes = cv2.imencode('.jpg', frame, encode_param)
            
            return jpeg_bytes.tobytes()
            
        except Exception as e:
            print(f"Capture error: {e}")
            return None
    
    def _capture_loop(self):
        """Background thread for continuous screen capture."""
        frame_interval = 1.0 / self.target_fps
        last_capture = time.time()
        
        while self.running:
            try:
                # Monitor CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.cpu_history.append(cpu_percent)
                if len(self.cpu_history) > 10:
                    self.cpu_history.pop(0)
                
                avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
                
                # Adaptive FPS adjustment based on CPU
                if avg_cpu > self.max_cpu_percent and self.adaptive_fps > 5:
                    self.adaptive_fps = max(5, self.adaptive_fps - 1)
                    frame_interval = 1.0 / self.adaptive_fps
                elif avg_cpu < self.max_cpu_percent * 0.7 and self.adaptive_fps < self.target_fps:
                    self.adaptive_fps = min(self.target_fps, self.adaptive_fps + 1)
                    frame_interval = 1.0 / self.adaptive_fps
                
                # Capture frame
                frame_data = self.capture_frame()
                
                if frame_data:
                    # Check bandwidth
                    current_time = time.time()
                    time_diff = current_time - self.last_bandwidth_check
                    
                    if time_diff >= 1.0:
                        self.bandwidth_usage = self.bandwidth_accumulator / time_diff
                        self.bandwidth_accumulator = 0
                        self.last_bandwidth_check = current_time
                        
                        # Reduce quality if bandwidth exceeded
                        if self.bandwidth_usage > self.max_bandwidth and self.jpeg_quality > 40:
                            self.jpeg_quality = max(40, self.jpeg_quality - 5)
                    
                    self.bandwidth_accumulator += len(frame_data)
                    
                    # Put frame in queue (non-blocking)
                    try:
                        self.frame_queue.put_nowait(frame_data)
                    except queue.Full:
                        # Drop oldest frame if queue is full
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame_data)
                        except queue.Empty:
                            pass
                
                # Update FPS counter
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_update >= 1.0:
                    self.current_fps = self.frame_count
                    self.frame_count = 0
                    self.last_fps_update = current_time
                
                # Sleep to maintain target FPS
                elapsed = time.time() - last_capture
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                last_capture = time.time()
                
            except Exception as e:
                print(f"Capture loop error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start background capture thread."""
        if not self.running:
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
    
    def stop(self):
        """Stop background capture thread."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
    
    def get_frame(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        Get the latest frame from the queue.
        
        Args:
            timeout: Maximum time to wait for a frame
            
        Returns:
            JPEG bytes or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_stats(self) -> dict:
        """
        Get current capture statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        return {
            "fps": self.current_fps,
            "adaptive_fps": self.adaptive_fps,
            "bandwidth_bps": self.bandwidth_usage,
            "jpeg_quality": self.jpeg_quality,
            "cpu_percent": sum(self.cpu_history) / len(self.cpu_history) if self.cpu_history else 0,
            "resolution": f"{self.width}x{self.height}"
        }
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()

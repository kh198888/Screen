"""
Main FastAPI application for the remote desktop monitoring server.
Provides WebSocket endpoints and serves the dashboard.
"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.security import HTTPBearer
from fastapi import Request
from fastapi.responses import JSONResponse
import uvicorn

try:
    from .database import get_database
    from .websocket import handle_client_websocket, handle_dashboard_websocket, get_connection_manager
    from .api import router as api_router
except ImportError:  # Supports `python main.py` from the server directory.
    from database import get_database
    from websocket import handle_client_websocket, handle_dashboard_websocket, get_connection_manager
    from api import router as api_router

# Environment variables
PORT = int(os.getenv("PORT", 8000))
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/monitoring.db")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Background task for cleanup
async def cleanup_task():
    """Background task to clean up old data and mark offline computers."""
    db = get_database()
    manager = get_connection_manager()
    
    while True:
        try:
            # Mark offline computers
            db.mark_offline_computers(timeout_seconds=30)
            
            # Clean up old data (keep 7 days of keyboard events, 1 day of frames)
            db.cleanup_old_data(keyboard_days=7, frame_days=1)
            
            logger.info("Cleanup task completed")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
        
        # Run every 5 minutes
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting monitoring server...")
    
    # Initialize database
    db = get_database()
    logger.info("Database initialized")
    
    # Start background cleanup task
    cleanup_task_instance = asyncio.create_task(cleanup_task())
    
    yield
    
    # Shutdown
    logger.info("Shutting down monitoring server...")
    
    # Cancel background task
    cleanup_task_instance.cancel()
    try:
        await cleanup_task_instance
    except asyncio.CancelledError:
        pass
    
    # Close database
    db.close()
    logger.info("Server shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Remote Desktop Monitoring Server",
    description="High-performance remote desktop monitoring system",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Uncomment for HTTPS in production
# app.add_middleware(HTTPSRedirectMiddleware)

# Rate limiting middleware (simplified)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware."""
    # In production, implement proper rate limiting with Redis or similar
    response = await call_next(request)
    return response


# Include API router
app.include_router(api_router, tags=["API"])


# WebSocket endpoints

@app.websocket("/ws")
async def websocket_client(
    websocket: WebSocket,
    mac_address: str = Query(..., description="Client MAC address")
):
    """
    WebSocket endpoint for monitoring clients.
    
    Args:
        websocket: WebSocket connection
        mac_address: Client MAC address for identification
    """
    db = get_database()
    
    # Get or create computer record
    computer = db.get_computer_by_mac(mac_address)
    if not computer:
        # Create temporary record (will be updated with device info)
        computer_id = db.upsert_computer({
            "mac_address": mac_address,
            "computer_name": "Unknown",
            "ip_address": "Unknown",
            "browser": "Unknown",
            "os": "Unknown",
            "resolution": "Unknown",
            "username": "Unknown"
        })
    else:
        computer_id = computer["id"]
    
    # Handle client connection
    await handle_client_websocket(websocket, computer_id, db)


@app.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    computer_id: int = Query(None, description="Optional computer ID to monitor")
):
    """
    WebSocket endpoint for dashboard viewers.
    
    Args:
        websocket: WebSocket connection
        computer_id: Optional computer ID to monitor
    """
    await handle_dashboard_websocket(websocket, computer_id)


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_PATH = BASE_DIR / "templates" / "dashboard.html"

# Static assets are optional in the current dashboard, so don't prevent the
# server from starting when an asset directory has not been created yet.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Serve dashboard
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the monitoring dashboard."""
    try:
        with TEMPLATE_PATH.open("r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1><p>Please ensure templates/dashboard.html exists</p>", status_code=404)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "monitoring-server"}


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


def main():
    """Main entry point for the server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        reload=False,  # Set to True for development
        log_level="info",
        ws_ping_interval=5,
        ws_ping_timeout=10,
        workers=1  # Increase for production (use with Gunicorn)
    )


if __name__ == "__main__":
    main()

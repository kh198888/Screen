# Remote Desktop Monitoring System

A high-performance, production-ready remote desktop monitoring web application built with Python 3.13, FastAPI, and modern web technologies.

## Features

### Client (Agent)
- **High-Performance Screen Capture**: Uses MSS for efficient screen capture at 5-10 FPS
- **Delta Frame Optimization**: Skips duplicate frames to reduce bandwidth
- **Adaptive Quality**: Automatically adjusts JPEG quality based on CPU and bandwidth
- **Keyboard Monitoring**: Captures keyboard events with timestamps and window context
- **Device Information**: Collects MAC address, IP, hostname, browser, OS, and more
- **Auto-Reconnection**: Automatically reconnects to server on connection loss
- **Low Resource Usage**: Optimized for <8% CPU and <120MB memory

### Server
- **Real-Time WebSocket**: Binary frame transfer for low-latency streaming
- **SQLite Database**: Efficient data persistence with proper indexing
- **REST API**: Full REST API for managing computers and retrieving data
- **Connection Management**: Handles 100+ simultaneous clients
- **Background Workers**: Automatic cleanup of old data
- **Dashboard**: Modern dark-themed web interface

### Dashboard
- **Live Screen Monitoring**: Real-time screen updates every 100ms
- **Computer List**: Searchable list with online status
- **Keyboard Event Log**: Real-time keyboard event monitoring with filtering
- **Performance Stats**: Resolution, FPS, CPU, memory, and connection quality
- **Responsive Design**: Works on desktop and tablet devices
- **Modern UI**: Dark theme with TailwindCSS styling

## Technology Stack

### Server
- Python 3.13
- FastAPI
- Uvicorn
- WebSockets
- SQLite
- asyncio

### Client
- Python 3.13
- MSS (screen capture)
- OpenCV (image processing)
- Pillow (image handling)
- pynput (keyboard capture)
- psutil (system monitoring)
- WebSockets

### Frontend
- HTML5
- TailwindCSS
- JavaScript (WebSocket API)
- Modern responsive design

## Project Structure

```
Screen_Monitering/
├── client/
│   ├── agent.py          # Main client orchestrator
│   ├── capture.py        # Screen capture with MSS
│   ├── keyboard.py       # Keyboard event capture
│   └── websocket.py      # WebSocket client
├── server/
│   ├── main.py           # FastAPI application
│   ├── websocket.py      # WebSocket server handler
│   ├── database.py       # SQLite database operations
│   └── api.py            # REST API endpoints
├── templates/
│   └── dashboard.html    # Web dashboard
├── static/               # Static assets
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
└── README.md            # This file
```

## Installation

### Prerequisites
- Python 3.13 or higher
- pip (Python package manager)
- Windows (for client) or Linux (for server)

### Server Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd Screen_Monitering
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the server**
```bash
cd server
python main.py
```

The server will start on `http://localhost:8000`

### Client Setup (Windows)

#### Option 1: Using Python

1. **Navigate to client directory**
```bash
cd client
```

2. **Run the agent**
```bash
python agent.py --server ws://localhost:8000/ws --fps 10 --quality 50
```

#### Option 2: Using Executable (Recommended)

A pre-built executable is available for easy deployment without Python installation.

**Building the executable:**

1. **Install PyInstaller**
```bash
pip install pyinstaller
```

2. **Build the executable**
```bash
python -m PyInstaller --onefile --console --name "MonitoringAgent" client/agent.py
```

Or use the provided batch script:
```bash
build_client.bat
```

3. **Run the executable**
```bash
cd dist
MonitoringAgent.exe --server ws://localhost:8000/ws --fps 10 --quality 50
```

**Executable features:**
- Single file - no dependencies required
- Works on Windows without Python installation
- Can be distributed to other computers
- Console mode shows status and errors

### Docker Deployment

1. **Build and run with Docker Compose**
```bash
docker-compose up -d
```

2. **Access the dashboard**
```
http://localhost:8000
```

## Configuration

### Client Options

```bash
python agent.py [OPTIONS]

Options:
  --server TEXT       WebSocket server URL [default: ws://localhost:8000/ws]
  --fps INTEGER       Target FPS for screen capture (5-10) [default: 10]
  --quality INTEGER   JPEG quality (40-60) [default: 50]
```

### Server Configuration

Edit `server/main.py` to configure:
- Host and port
- Database path
- CORS settings
- Rate limiting
- JWT authentication

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### API Endpoints

#### Computers
- `GET /api/computers` - Get all computers
- `GET /api/computers/{id}` - Get specific computer
- `GET /api/computers/{id}/keyboard-events` - Get keyboard events
- `GET /api/computers/{id}/frames` - Get frame records
- `POST /api/computers/{id}/command` - Send command to computer

#### Server
- `GET /api/stats` - Get server statistics
- `POST /api/cleanup` - Clean up old data

#### WebSocket
- `WS /ws?mac_address=xxx` - Client connection
- `WS /ws/dashboard?computer_id=xxx` - Dashboard connection

## Database Schema

### computers
- `id` - Primary key
- `computer_name` - Computer hostname
- `mac_address` - MAC address (unique)
- `ip_address` - IP address
- `country` - Country (optional)
- `browser` - Default browser
- `os` - Operating system
- `resolution` - Screen resolution
- `username` - Windows username
- `online` - Online status
- `last_seen` - Last seen timestamp

### keyboard_events
- `id` - Primary key
- `computer_id` - Foreign key to computers
- `key` - Key pressed
- `window` - Active window title
- `time` - Event timestamp

### frames
- `id` - Primary key
- `computer_id` - Foreign key to computers
- `image_path` - Path to saved image
- `time` - Frame timestamp

## Performance Optimization

### Client
- **Delta Frame Detection**: Skips duplicate frames using MD5 hashing
- **Adaptive FPS**: Reduces FPS when CPU usage exceeds 8%
- **Dynamic Quality**: Lowers JPEG quality when bandwidth exceeds 2MB/sec
- **Thread Pool**: Separate threads for capture and transmission
- **Queue Management**: Bounded queues prevent memory overflow

### Server
- **Connection Pooling**: Efficient WebSocket connection management
- **Memory Caching**: Caches latest frames and stats
- **Database Indexing**: Proper indexes on frequently queried columns
- **Background Cleanup**: Automatic cleanup of old data
- **WAL Mode**: SQLite Write-Ahead Logging for better concurrency

## Security Features

- **JWT Authentication**: Token-based authentication for API endpoints
- **CORS Protection**: Configurable CORS settings
- **Rate Limiting**: Built-in rate limiting middleware
- **Input Validation**: Pydantic models for request validation
- **SQL Injection Protection**: Parameterized queries
- **XSS Protection**: HTML escaping in dashboard

## Monitoring 100+ Clients

The system is optimized to handle 100+ simultaneous clients:

1. **Async Architecture**: All I/O operations are non-blocking
2. **Efficient Protocols**: WebSocket with binary frame transfer
3. **Resource Management**: Adaptive quality based on system load
4. **Connection Pooling**: Efficient connection management
5. **Database Optimization**: WAL mode and proper indexing
6. **Background Workers**: Separate tasks for cleanup and maintenance

## Troubleshooting

### Client won't connect
- Check server URL is correct
- Verify server is running
- Check firewall settings
- Ensure WebSocket port (8000) is open

### High CPU usage
- Reduce target FPS: `--fps 5`
- Increase JPEG quality: `--quality 60`
- Check for other resource-intensive applications

### Screen capture not working
- Ensure MSS is installed correctly
- Check display settings
- Run as administrator on Windows

### Keyboard events not captured
- Run as administrator on Windows
- Check antivirus/security software
- Verify pynput installation

## Production Deployment

### Using Docker Compose

```bash
docker-compose up -d
```

### Using Nginx (Optional)

1. Create `nginx.conf`:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream monitoring {
        server server:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        location / {
            proxy_pass http://monitoring;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }
}
```

2. Enable Nginx profile:
```bash
docker-compose --profile production up -d
```

### HTTPS Configuration

1. Obtain SSL certificates
2. Update `nginx.conf` for HTTPS
3. Uncomment HTTPS middleware in `server/main.py`

### Railway Deployment

Railway is a cloud platform that makes it easy to deploy Python applications.

1. **Prepare your repository**
   - Push your code to a Git repository (GitHub, GitLab, or Bitbucket)
   - Ensure `railway.json` is in the root directory

2. **Create a new Railway project**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository

3. **Configure environment variables**
   Railway will automatically detect the Python project. Set these environment variables:
   - `PORT`: Railway sets this automatically (default: 8000)
   - `DATABASE_PATH`: `/data/monitoring.db` (Railway's persistent storage)

4. **Deploy**
   - Railway will automatically build and deploy your application
   - The build process uses the `railway.json` configuration
   - Once deployed, you'll get a public URL (e.g., `https://your-app.railway.app`)

5. **Configure client connection**
   Update your client to connect to the Railway URL:
   ```bash
   python agent.py --server wss://your-app.railway.app/ws --fps 10 --quality 50
   ```

6. **Persistent storage**
   - Railway provides ephemeral storage by default
   - For database persistence, add a Railway volume:
     - Go to your project settings
     - Add a new volume
     - Mount it to `/data`
     - Set `DATABASE_PATH=/data/monitoring.db`

7. **Custom domain (optional)**
   - Go to project settings → Domains
   - Add your custom domain
   - Update DNS records as instructed by Railway

**Railway-specific notes:**
- The server automatically uses the `PORT` environment variable provided by Railway
- Database is stored in `/data` directory for persistence
- Health checks are configured in `railway.json`
- Railway automatically handles SSL/HTTPS

## License

This project is provided as-is for educational and monitoring purposes.

## Disclaimer

This software is intended for legitimate monitoring purposes only. Users are responsible for ensuring compliance with applicable laws and regulations regarding privacy and consent. Unauthorized monitoring of computers may be illegal in many jurisdictions.

## Support

For issues and questions, please refer to the project documentation or contact the development team.

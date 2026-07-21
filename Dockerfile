# Multi-stage Dockerfile for Remote Desktop Monitoring System

# Stage 1: Server
FROM python:3.13-slim AS server

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
COPY start.py .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server/ ./server/
COPY templates/ ./templates/
COPY static/ ./static/

# Create directories for data
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run server
CMD ["python", "-m", "server.main"]

# Stage 2: Client (Windows-specific, for reference)
# Note: This stage is for Linux clients only. Windows clients should run natively.
FROM python:3.13-slim AS client

WORKDIR /app

# Install system dependencies for screen capture
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libx11-dev \
    libxtst-dev \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy client code
COPY client/ ./client/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run client (example)
# CMD ["python", "-m", "client.agent", "--server", "ws://server:8000/ws"]

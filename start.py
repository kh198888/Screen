"""
Deployment entrypoint for the monitoring server.

This script makes the repository root explicit and imports the server application
from the local `server` directory so deployment platforms can start the app
without depending on the current working directory.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from server.main import main

if __name__ == "__main__":
    main()

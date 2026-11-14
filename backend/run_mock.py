import os
import sys
from pathlib import Path

# Ensure the backend directory is available for imports
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Force mock mode
os.environ["MOCK_MODE"] = "true"

# Import the FastAPI application
from app.main import app

import uvicorn


if __name__ == "__main__":
    print("Starting SDE-4 backend in MOCK mode...")
    print("API documentation: http://127.0.0.1:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
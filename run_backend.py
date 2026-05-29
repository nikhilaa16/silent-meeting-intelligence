"""
Run the FastAPI backend server.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,   # Auto-reload on code changes during development
        reload_dirs=["backend"], # ONLY watch backend code to prevent restarts on file uploads
        log_level="info",
    )

#!/usr/bin/env python3
"""
Start script for the Workflow Automation Backend
"""
import os
import sys
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_server():
    """Start the FastAPI server"""
    try:
        # Set environment defaults
        os.environ.setdefault("DEBUG", "True")
        os.environ.setdefault("ENV", "development")
        
        # Check if main module can be imported
        try:
            import main
            logger.info("Main module imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import main module: {e}")
            return
        
        # Get port from environment or use default
        port = int(os.environ.get("PORT", 8000))
        host = os.environ.get("HOST", "0.0.0.0")
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Start the server
        uvicorn.run(
            "main:app", 
            host=host, 
            port=port, 
            reload=True,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server() 
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("workflow_api.log")
    ]
)
logger = logging.getLogger("workflow_api")

# Simple settings for minimal setup
class SimpleSettings:
    DEBUG = True
    CORS_ORIGINS = ["http://localhost:5173", "http://localhost:5174", "http://localhost", "http://localhost:80"]

settings = SimpleSettings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup operations
    logger.info("Starting Minimal Workflow Automation API")
    yield
    # Shutdown operations
    logger.info("Shutting down Minimal Workflow Automation API")

app = FastAPI(title="FlowMind AI API - Minimal", lifespan=lifespan)

# Add exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request validation errors"""
    error_details = []
    for error in exc.errors():
        error_details.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
        
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request parameters",
            "error_code": "VALIDATION_ERROR",
            "data": {"errors": error_details}
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for standard HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": f"HTTP_{exc.status_code}"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error_code": "INTERNAL_ERROR",
            "data": {"error": str(exc)} if settings.DEBUG else {}
        }
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Length", "X-Process-Time"],
    max_age=600  # 10 minutes
)

# Add middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    request_id = str(int(time.time() * 1000))
    logger.info(f"Request {request_id} - {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request {request_id} completed in {process_time:.3f}s - Status: {response.status_code}")
        
        # Add timing header to response
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request {request_id} failed in {process_time:.3f}s: {str(e)}")
        return JSONResponse(
            status_code=500, 
            content={"detail": "Internal Server Error", "error": str(e)}
        )

# Basic routes
@app.get("/")
async def root():
    return {"message": "Welcome to the Workflow Automation API", "status": "running", "version": "minimal"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "workflow-automation-backend"}

@app.get("/api/health")
async def api_health_check():
    return {"status": "healthy", "service": "workflow-automation-backend", "api": "ready"}

# Minimal workflow execution endpoint
@app.post("/api/workflows/execute")
async def execute_workflow(request: Request):
    try:
        data = await request.json()
        logger.info(f"Workflow execution request: {data}")
        
        # For now, return a mock response
        return {
            "success": True,
            "message": "Workflow execution endpoint is available but not fully implemented",
            "data": {
                "workflow_id": data.get("workflow_id", "unknown"),
                "status": "mock_execution",
                "note": "Backend server is running but workflow execution requires full setup"
            }
        }
    except Exception as e:
        logger.error(f"Error in workflow execution: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": "Workflow execution failed",
                "error": str(e)
            }
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main_minimal:app", host="0.0.0.0", port=port, reload=True) 
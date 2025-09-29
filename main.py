from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
from qdrant_client import QdrantClient
from contextlib import asynccontextmanager
from config import settings
from routers import auth, workflows, users, nodes, knowledge_base, database, integrations, slack, google_auth  # Added google_auth
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
import logging
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from routers.exceptions import WorkflowException
from middleware.rate_limit import RateLimitMiddleware
import os
import time
from typing import Dict, Any
from pathlib import Path

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

# Add exception handlers
def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WorkflowException)
    async def workflow_exception_handler(request: Request, exc: WorkflowException) -> JSONResponse:
        """Handler for custom workflow exceptions"""
        response = {
            "detail": exc.detail,
            "error_code": exc.error_code,
        }
        
        # Include additional data if available
        if hasattr(exc, "data") and exc.data:
            response["data"] = exc.data
            
        return JSONResponse(
            status_code=exc.status_code,
            content=response
        )
        
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup operations
    logger.info("Starting Workflow Automation API")
    
    # MongoDB connection
    app.mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.mongodb = app.mongodb_client[settings.MONGODB_DB_NAME]
    
    # Redis connection
    app.redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True
    )
    
    # Qdrant connection with proper SSL configuration
    qdrant_url = settings.QDRANT_URL
    use_https = qdrant_url.startswith("https://")
    is_localhost = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
    
    # For localhost development, don't use API key to avoid insecure connection warnings
    qdrant_api_key = None if is_localhost else settings.QDRANT_API_KEY
    
    if settings.QDRANT_API_KEY and is_localhost:
        logger.info("Qdrant API key ignored for localhost development to avoid insecure connection warnings")
    elif settings.QDRANT_API_KEY and not use_https:
        logger.warning("Qdrant API key provided with HTTP URL. Consider using HTTPS in production.")
    
    app.qdrant = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        https=use_https,  # Only enable HTTPS if URL uses https://
        prefer_grpc=False,  # Use HTTP REST API
        timeout=60.0  # Set appropriate timeout
    )
    
    yield
    
    # Shutdown operations
    logger.info("Shutting down Workflow Automation API")
    
    # Cleanup
    app.mongodb_client.close()
    app.redis.close()
    app.qdrant.close()

app = FastAPI(title="FlowMind AI API", lifespan=lifespan)

# Add debug flag
app.debug = settings.DEBUG

# Add exception handlers
add_exception_handlers(app)

# Determine if we're using HTTPS (for Secure cookie flag)
is_https = settings.FRONTEND_URL.startswith("https")

# Session middleware must be first
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.OAUTH2_SECRET,
    session_cookie="flowmind_session",
    max_age=86400,  # Increase to 24 hours for better persistence
    # For cross-site cookies (deployed frontend on different origin), browsers require SameSite=None and Secure
    same_site=("none" if is_https else "lax"),  # Use None+Secure for HTTPS deployments, lax for local dev
    https_only=is_https,  # Set based on HTTPS usage
    path="/",  # Make sure cookie is available for all paths
    domain=settings.SESSION_COOKIE_DOMAIN or None  # Use configured domain if provided
)

# Add rate limiting middleware - after session middleware for user identification
@app.on_event("startup")
async def startup_event():
    # Add rate limiting middleware
    if settings.ENABLE_RATE_LIMITING:
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=app.redis,
            requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
            requests_per_hour=settings.RATE_LIMIT_PER_HOUR,
            exclude_paths=["/api/auth", "/"]  # Don't rate limit authentication endpoints
        )
        logger.info("Rate limiting middleware enabled")

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

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(nodes.router)
app.include_router(knowledge_base.router)
app.include_router(database.router)
app.include_router(integrations.router)
app.include_router(slack.router)
app.include_router(google_auth.router, prefix="/api/google", tags=["Google Services"])  # Fixed Google auth router prefix

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

# Create templates directory if it doesn't exist
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)

# Comment out jinja2 imports and debug prints
# import jinja2
# import sys
# print(f"Python path: {sys.path}")
# print(f"Jinja2 version: {jinja2.__version__}")

# Comment out Jinja2Templates initialization
# templates = Jinja2Templates(directory=str(templates_dir))

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(nodes.router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(knowledge_base.router, tags=["Knowledge Base"])
app.include_router(database.router, prefix="/api/database", tags=["Database"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])  # Added integrations router
# Temporarily commented out: app.include_router(google_drive.router, tags=["Google Drive"])

# Modified route for the integrations UI to not use templates
@app.get("/integrations", response_class=JSONResponse)
async def integrations_page(request: Request):
    return JSONResponse({
        "message": "Integrations UI temporarily unavailable. Template functionality will be fixed later."
    })

# Add route for the integrations guide
@app.get("/integrations/guide", response_class=PlainTextResponse)
async def integrations_guide():
    guide_path = Path(__file__).parent / "integrations_guide.md"
    if guide_path.exists():
        with open(guide_path, "r") as f:
            content = f.read()
        return content
    return "# Integration Guide\n\nGuide content not available."

@app.get("/")
async def root():
    return {"message": "Welcome to the Workflow Automation API"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
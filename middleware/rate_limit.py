from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi.responses import JSONResponse
from redis import Redis
import time
import hashlib
from typing import Dict, Optional, Callable, Tuple
import logging
from routers.exceptions import RateLimitExceededError

logger = logging.getLogger("workflow_api")

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app,
        redis_client: Redis,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        exclude_paths: Optional[list] = None,
        get_user_id: Optional[Callable[[Request], str]] = None
    ):
        super().__init__(app)
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.exclude_paths = exclude_paths or []
        self.get_user_id = get_user_id or self._get_default_user_id
        
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
            
        # Get user identifier (IP or user ID)
        user_id = await self.get_user_id(request)
        
        # Check rate limits
        try:
            await self._check_rate_limits(user_id)
        except RateLimitExceededError as exc:
            # Set headers for rate limit response
            reset_time = exc.data.get("reset_time", 0)
            headers = {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(max(1, reset_time - int(time.time())))
            }
            
            return JSONResponse(
                status_code=429,
                content={
                    "detail": exc.detail,
                    "error_code": exc.error_code,
                    "data": exc.data
                },
                headers=headers
            )
            
        # Process the request
        response = await call_next(request)
        return response
        
    async def _check_rate_limits(self, user_id: str) -> None:
        """Check if user has exceeded rate limits"""
        now = int(time.time())
        minute_key = f"rate_limit:minute:{user_id}:{now // 60}"
        hour_key = f"rate_limit:hour:{user_id}:{now // 3600}"
        
        # Pipeline Redis commands for efficiency
        pipe = self.redis.pipeline()
        
        # Increment counters
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)  # Expire after 1 minute
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)  # Expire after 1 hour
        
        # Execute pipeline
        results = pipe.execute()
        minute_count, _, hour_count, _ = results
        
        # Check limits
        if minute_count > self.requests_per_minute:
            next_minute = (now // 60 + 1) * 60
            logger.warning(f"Rate limit exceeded (per minute) for user {user_id}")
            raise RateLimitExceededError(
                limit_type="requests per minute",
                reset_time=next_minute
            )
            
        if hour_count > self.requests_per_hour:
            next_hour = (now // 3600 + 1) * 3600
            logger.warning(f"Rate limit exceeded (per hour) for user {user_id}")
            raise RateLimitExceededError(
                limit_type="requests per hour",
                reset_time=next_hour
            )
    
    async def _get_default_user_id(self, request: Request) -> str:
        """Get a user identifier from request - defaults to IP address"""
        # Try to get user ID from session
        if "user_id" in request.session:
            return str(request.session["user_id"])
            
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
            
        # Anonymize IP by hashing
        return hashlib.md5(ip.encode()).hexdigest() 
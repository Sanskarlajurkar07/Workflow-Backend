"""
Enhanced Error Recovery System for Smart Database
Provides robust failure handling, retry mechanisms, and circuit breakers
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict, List
from functools import wraps
from dataclasses import dataclass
from enum import Enum
import aiohttp
from qdrant_client.http.exceptions import ApiException
from pymongo.errors import PyMongoError
import redis.exceptions

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    QDRANT_CONNECTION = "qdrant_connection"
    MONGODB_CONNECTION = "mongodb_connection"
    REDIS_CONNECTION = "redis_connection"
    EMBEDDING_API = "embedding_api"
    DOCUMENT_PROCESSING = "document_processing"
    SEARCH_TIMEOUT = "search_timeout"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"

@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    reset_timeout: int = 60
    half_open_max_calls: int = 3

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.config.reset_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN

class ErrorRecoveryManager:
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_configs: Dict[ErrorType, RetryConfig] = {
            ErrorType.QDRANT_CONNECTION: RetryConfig(max_attempts=5, base_delay=2.0),
            ErrorType.MONGODB_CONNECTION: RetryConfig(max_attempts=3, base_delay=1.0),
            ErrorType.REDIS_CONNECTION: RetryConfig(max_attempts=3, base_delay=0.5),
            ErrorType.EMBEDDING_API: RetryConfig(max_attempts=3, base_delay=5.0, max_delay=30.0),
            ErrorType.DOCUMENT_PROCESSING: RetryConfig(max_attempts=2, base_delay=1.0),
            ErrorType.SEARCH_TIMEOUT: RetryConfig(max_attempts=2, base_delay=0.5),
            ErrorType.RATE_LIMIT: RetryConfig(max_attempts=3, base_delay=10.0, max_delay=60.0),
        }

    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        if service_name not in self.circuit_breakers:
            config = CircuitBreakerConfig()
            self.circuit_breakers[service_name] = CircuitBreaker(config)
        return self.circuit_breakers[service_name]

    def classify_error(self, exception: Exception) -> ErrorType:
        """Classify error type for appropriate retry strategy"""
        if isinstance(exception, ApiException):
            return ErrorType.QDRANT_CONNECTION
        elif isinstance(exception, PyMongoError):
            return ErrorType.MONGODB_CONNECTION
        elif isinstance(exception, redis.exceptions.RedisError):
            return ErrorType.REDIS_CONNECTION
        elif isinstance(exception, aiohttp.ClientError):
            return ErrorType.EMBEDDING_API
        elif "timeout" in str(exception).lower():
            return ErrorType.SEARCH_TIMEOUT
        elif "rate limit" in str(exception).lower():
            return ErrorType.RATE_LIMIT
        else:
            return ErrorType.UNKNOWN

    async def execute_with_retry(
        self, 
        func: Callable, 
        *args, 
        error_type: Optional[ErrorType] = None,
        custom_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic and exponential backoff"""
        
        last_exception = None
        config = custom_config or self.retry_configs.get(error_type, RetryConfig())
        
        for attempt in range(config.max_attempts):
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Log successful retry if not first attempt
                if attempt > 0:
                    logger.info(f"Function succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Classify error if not provided
                if error_type is None:
                    error_type = self.classify_error(e)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {str(e)}"
                )
                
                # Don't wait after the last attempt
                if attempt < config.max_attempts - 1:
                    delay = self._calculate_delay(attempt, config)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
        
        # All attempts failed
        logger.error(f"All {config.max_attempts} attempts failed. Last error: {str(last_exception)}")
        raise last_exception

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay with exponential backoff and jitter"""
        delay = config.base_delay * (config.exponential_base ** attempt)
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            import random
            # Add random jitter (±25%)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)

    async def execute_with_circuit_breaker(
        self, 
        service_name: str, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        if asyncio.iscoroutinefunction(func):
            return await circuit_breaker.call(func, *args, **kwargs)
        else:
            return circuit_breaker.call(func, *args, **kwargs)

    async def execute_with_full_protection(
        self,
        func: Callable,
        service_name: str,
        *args,
        error_type: Optional[ErrorType] = None,
        custom_config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """Execute function with both retry logic and circuit breaker protection"""
        
        async def protected_func(*args, **kwargs):
            return await self.execute_with_circuit_breaker(
                service_name, func, *args, **kwargs
            )
        
        return await self.execute_with_retry(
            protected_func, 
            *args, 
            error_type=error_type,
            custom_config=custom_config,
            **kwargs
        )

# Decorators for easy use
def with_retry(
    error_type: Optional[ErrorType] = None,
    config: Optional[RetryConfig] = None
):
    """Decorator for adding retry logic to functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            recovery_manager = ErrorRecoveryManager()
            return await recovery_manager.execute_with_retry(
                func, *args, error_type=error_type, custom_config=config, **kwargs
            )
        return wrapper
    return decorator

def with_circuit_breaker(service_name: str):
    """Decorator for adding circuit breaker protection"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            recovery_manager = ErrorRecoveryManager()
            return await recovery_manager.execute_with_circuit_breaker(
                service_name, func, *args, **kwargs
            )
        return wrapper
    return decorator

def with_full_protection(
    service_name: str,
    error_type: Optional[ErrorType] = None,
    config: Optional[RetryConfig] = None
):
    """Decorator for full error protection (retry + circuit breaker)"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            recovery_manager = ErrorRecoveryManager()
            return await recovery_manager.execute_with_full_protection(
                func, service_name, *args, 
                error_type=error_type, custom_config=config, **kwargs
            )
        return wrapper
    return decorator

# Global instance
error_recovery = ErrorRecoveryManager()

# Health check functions
async def check_qdrant_health(qdrant_client) -> Dict[str, Any]:
    """Check Qdrant service health"""
    try:
        collections = await error_recovery.execute_with_retry(
            qdrant_client.get_collections,
            error_type=ErrorType.QDRANT_CONNECTION
        )
        return {"status": "healthy", "collections_count": len(collections.collections)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_mongodb_health(db) -> Dict[str, Any]:
    """Check MongoDB service health"""
    try:
        await error_recovery.execute_with_retry(
            db.admin.command,
            "ping",
            error_type=ErrorType.MONGODB_CONNECTION
        )
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_redis_health(redis_client) -> Dict[str, Any]:
    """Check Redis service health"""
    try:
        await error_recovery.execute_with_retry(
            redis_client.ping,
            error_type=ErrorType.REDIS_CONNECTION
        )
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)} 
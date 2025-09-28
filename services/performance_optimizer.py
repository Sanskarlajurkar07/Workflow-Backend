"""
Performance Optimization System for Smart Database
Provides caching, connection pooling, batch processing, and async optimizations
"""

import asyncio
import time
import hashlib
import json
import pickle
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    value: Any
    timestamp: datetime
    ttl_seconds: int
    access_count: int = 0
    
    def is_expired(self) -> bool:
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

class SmartCache:
    """Intelligent multi-level caching system"""
    
    def __init__(self, max_memory_items: int = 1000, redis_client: Optional[redis.Redis] = None):
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.max_memory_items = max_memory_items
        self.redis_client = redis_client
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
        self._lock = threading.Lock()

    def _generate_key(self, key_parts: List[str]) -> str:
        """Generate consistent cache key"""
        key_string = "|".join(str(part) for part in key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def get(self, key_parts: List[str], default: Any = None) -> Any:
        """Get value from cache with fallback hierarchy"""
        cache_key = self._generate_key(key_parts)
        
        # Try memory cache first
        with self._lock:
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if not entry.is_expired():
                    entry.access_count += 1
                    self.cache_stats["hits"] += 1
                    return entry.value
                else:
                    # Remove expired entry
                    del self.memory_cache[cache_key]

        # Try Redis cache
        if self.redis_client:
            try:
                redis_value = await self.redis_client.get(f"cache:{cache_key}")
                if redis_value:
                    value = pickle.loads(redis_value)
                    # Promote to memory cache
                    await self.set(key_parts, value, ttl_seconds=300)  # 5 min memory TTL
                    self.cache_stats["hits"] += 1
                    return value
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        self.cache_stats["misses"] += 1
        return default

    async def set(self, key_parts: List[str], value: Any, ttl_seconds: int = 3600):
        """Set value in cache with TTL"""
        cache_key = self._generate_key(key_parts)
        
        # Set in memory cache
        with self._lock:
            # Evict if necessary
            if len(self.memory_cache) >= self.max_memory_items:
                await self._evict_lru()
            
            self.memory_cache[cache_key] = CacheEntry(
                value=value,
                timestamp=datetime.now(),
                ttl_seconds=ttl_seconds
            )

        # Set in Redis cache with longer TTL
        if self.redis_client:
            try:
                redis_ttl = max(ttl_seconds, 3600)  # At least 1 hour in Redis
                await self.redis_client.setex(
                    f"cache:{cache_key}",
                    redis_ttl,
                    pickle.dumps(value)
                )
            except Exception as e:
                logger.warning(f"Redis cache set error: {e}")

    async def _evict_lru(self):
        """Evict least recently used items"""
        if not self.memory_cache:
            return
            
        # Sort by access count (LRU approximation)
        sorted_items = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].access_count
        )
        
        # Remove oldest 10% of items
        evict_count = max(1, len(sorted_items) // 10)
        for i in range(evict_count):
            key, _ = sorted_items[i]
            del self.memory_cache[key]
            self.cache_stats["evictions"] += 1

    async def invalidate(self, key_parts: List[str]):
        """Invalidate cache entry"""
        cache_key = self._generate_key(key_parts)
        
        with self._lock:
            self.memory_cache.pop(cache_key, None)
        
        if self.redis_client:
            try:
                await self.redis_client.delete(f"cache:{cache_key}")
            except Exception as e:
                logger.warning(f"Redis invalidation error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "hit_rate": hit_rate,
            "memory_items": len(self.memory_cache),
            "max_memory_items": self.max_memory_items,
            **self.cache_stats
        }

class ConnectionPoolManager:
    """Manages connection pools for various services"""
    
    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.pool_configs = {
            "mongodb": {
                "max_pool_size": 100,
                "min_pool_size": 10,
                "max_idle_time_ms": 30000
            },
            "qdrant": {
                "pool_size": 20,
                "timeout": 30
            },
            "redis": {
                "max_connections": 50,
                "retry_on_timeout": True
            }
        }

    async def get_mongodb_client(self, connection_string: str) -> AsyncIOMotorClient:
        """Get MongoDB client with connection pooling"""
        pool_key = f"mongodb_{hashlib.md5(connection_string.encode()).hexdigest()}"
        
        if pool_key not in self.pools:
            config = self.pool_configs["mongodb"]
            self.pools[pool_key] = AsyncIOMotorClient(
                connection_string,
                maxPoolSize=config["max_pool_size"],
                minPoolSize=config["min_pool_size"],
                maxIdleTimeMS=config["max_idle_time_ms"]
            )
        
        return self.pools[pool_key]

    async def get_redis_pool(self, redis_url: str) -> redis.Redis:
        """Get Redis connection pool"""
        pool_key = f"redis_{hashlib.md5(redis_url.encode()).hexdigest()}"
        
        if pool_key not in self.pools:
            config = self.pool_configs["redis"]
            self.pools[pool_key] = redis.from_url(
                redis_url,
                max_connections=config["max_connections"],
                retry_on_timeout=config["retry_on_timeout"]
            )
        
        return self.pools[pool_key]

class BatchProcessor:
    """Efficient batch processing for operations"""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches: Dict[str, List] = {}
        self.processors: Dict[str, Callable] = {}
        self.last_flush: Dict[str, float] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []

    def register_processor(self, operation_name: str, processor_func: Callable):
        """Register a batch processor function"""
        self.processors[operation_name] = processor_func
        self.batches[operation_name] = []
        self.last_flush[operation_name] = time.time()

    async def add_to_batch(self, operation_name: str, item: Any):
        """Add item to batch for processing"""
        if operation_name not in self.batches:
            raise ValueError(f"No processor registered for {operation_name}")
        
        self.batches[operation_name].append(item)
        
        # Check if batch is full
        if len(self.batches[operation_name]) >= self.batch_size:
            await self._flush_batch(operation_name)

    async def _flush_batch(self, operation_name: str):
        """Flush a specific batch"""
        if not self.batches[operation_name]:
            return
        
        batch = self.batches[operation_name].copy()
        self.batches[operation_name].clear()
        self.last_flush[operation_name] = time.time()
        
        try:
            processor = self.processors[operation_name]
            if asyncio.iscoroutinefunction(processor):
                await processor(batch)
            else:
                await asyncio.get_event_loop().run_in_executor(None, processor, batch)
        except Exception as e:
            logger.error(f"Error processing batch {operation_name}: {e}")

    async def start(self):
        """Start batch processing"""
        self._running = True
        
        # Start flush timer for each operation
        for operation_name in self.processors:
            task = asyncio.create_task(self._flush_timer(operation_name))
            self._tasks.append(task)

    async def stop(self):
        """Stop batch processing and flush remaining items"""
        self._running = False
        
        # Cancel timer tasks
        for task in self._tasks:
            task.cancel()
        
        # Flush all remaining batches
        for operation_name in self.batches:
            await self._flush_batch(operation_name)

    async def _flush_timer(self, operation_name: str):
        """Timer-based flushing"""
        while self._running:
            await asyncio.sleep(1)  # Check every second
            
            time_since_flush = time.time() - self.last_flush[operation_name]
            if time_since_flush >= self.flush_interval and self.batches[operation_name]:
                await self._flush_batch(operation_name)

class EmbeddingCache:
    """Specialized cache for embeddings"""
    
    def __init__(self, cache: SmartCache):
        self.cache = cache

    async def get_embedding(self, text: str, model: str) -> Optional[List[float]]:
        """Get cached embedding"""
        key_parts = ["embedding", model, text]
        return await self.cache.get(key_parts)

    async def set_embedding(self, text: str, model: str, embedding: List[float], ttl_seconds: int = 86400):
        """Cache embedding (24h default TTL)"""
        key_parts = ["embedding", model, text]
        await self.cache.set(key_parts, embedding, ttl_seconds)

    async def get_batch_embeddings(self, texts: List[str], model: str) -> Dict[str, Optional[List[float]]]:
        """Get multiple embeddings from cache"""
        results = {}
        for text in texts:
            embedding = await self.get_embedding(text, model)
            results[text] = embedding
        return results

    async def set_batch_embeddings(self, embeddings: Dict[str, List[float]], model: str, ttl_seconds: int = 86400):
        """Cache multiple embeddings"""
        for text, embedding in embeddings.items():
            await self.set_embedding(text, model, embedding, ttl_seconds)

class SearchCache:
    """Specialized cache for search results"""
    
    def __init__(self, cache: SmartCache):
        self.cache = cache

    async def get_search_results(self, collection_name: str, query_embedding: List[float], top_k: int) -> Optional[List[Dict]]:
        """Get cached search results"""
        # Use embedding hash as key component
        embedding_hash = hashlib.md5(json.dumps(query_embedding).encode()).hexdigest()
        key_parts = ["search", collection_name, embedding_hash, str(top_k)]
        return await self.cache.get(key_parts)

    async def set_search_results(self, collection_name: str, query_embedding: List[float], top_k: int, results: List[Dict], ttl_seconds: int = 1800):
        """Cache search results (30min default TTL)"""
        embedding_hash = hashlib.md5(json.dumps(query_embedding).encode()).hexdigest()
        key_parts = ["search", collection_name, embedding_hash, str(top_k)]
        await self.cache.set(key_parts, results, ttl_seconds)

class AsyncTaskQueue:
    """Async task queue for background processing"""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.task_queue = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def start(self):
        """Start the task queue workers"""
        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(f"worker-{i}"))
            for i in range(self.max_workers)
        ]

    async def stop(self):
        """Stop the task queue workers"""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)

    async def enqueue(self, func: Callable, *args, **kwargs):
        """Enqueue a task for processing"""
        task_data = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "timestamp": time.time()
        }
        await self.task_queue.put(task_data)

    async def _worker(self, worker_name: str):
        """Worker process for handling tasks"""
        while self.running:
            try:
                # Wait for task with timeout
                task_data = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                func = task_data["func"]
                args = task_data["args"]
                kwargs = task_data["kwargs"]
                
                # Execute task
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    # Run CPU-bound tasks in thread pool
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, func, *args
                    )
                
                # Mark task as done
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                # No tasks available, continue
                continue
            except Exception as e:
                logger.error(f"Error in worker {worker_name}: {e}")

# Global instances
connection_pool_manager = ConnectionPoolManager()
batch_processor = BatchProcessor()
async_task_queue = AsyncTaskQueue()

# Initialize smart cache (will be configured with Redis in main app)
smart_cache = SmartCache()
embedding_cache = EmbeddingCache(smart_cache)
search_cache = SearchCache(smart_cache)

# Performance utilities
def optimize_numpy_operations():
    """Optimize NumPy operations for better performance"""
    import os
    
    # Set optimal thread counts for NumPy
    cpu_count = os.cpu_count()
    optimal_threads = min(cpu_count, 8)  # Don't use too many threads
    
    os.environ["OMP_NUM_THREADS"] = str(optimal_threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(optimal_threads)
    os.environ["MKL_NUM_THREADS"] = str(optimal_threads)
    os.environ["VECLIB_MAXIMUM_THREADS"] = str(optimal_threads)
    os.environ["NUMEXPR_NUM_THREADS"] = str(optimal_threads)

async def initialize_performance_systems(redis_url: Optional[str] = None):
    """Initialize all performance optimization systems"""
    global smart_cache
    
    # Setup Redis if available
    if redis_url:
        try:
            redis_client = await connection_pool_manager.get_redis_pool(redis_url)
            smart_cache = SmartCache(redis_client=redis_client)
            logger.info("Performance optimization with Redis enabled")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}")
    
    # Start batch processor
    await batch_processor.start()
    
    # Start async task queue
    await async_task_queue.start()
    
    # Optimize NumPy
    optimize_numpy_operations()
    
    logger.info("Performance optimization systems initialized")

async def shutdown_performance_systems():
    """Gracefully shutdown performance systems"""
    await batch_processor.stop()
    await async_task_queue.stop()
    logger.info("Performance optimization systems shut down")

# Decorators for easy performance optimization
def cached(ttl_seconds: int = 3600, key_func: Optional[Callable] = None):
    """Decorator for caching function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key_parts = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__, str(args), str(kwargs)]
            
            # Try cache first
            result = await smart_cache.get(key_parts)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await smart_cache.set(key_parts, result, ttl_seconds)
            
            return result
        return wrapper
    return decorator

def batched(operation_name: str, batch_size: int = 100):
    """Decorator for batching operations"""
    def decorator(func):
        # Register processor
        batch_processor.register_processor(operation_name, func)
        
        async def wrapper(item):
            await batch_processor.add_to_batch(operation_name, item)
        return wrapper
    return decorator 
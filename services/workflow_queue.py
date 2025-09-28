import asyncio
import json
import logging
import redis
import uuid
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import pickle
import traceback

logger = logging.getLogger("workflow_api")

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class WorkflowJob:
    job_id: str
    workflow_id: str
    user_id: str
    priority: JobPriority
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in ['created_at', 'scheduled_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowJob':
        # Convert ISO strings back to datetime objects
        for field in ['created_at', 'scheduled_at', 'started_at', 'completed_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        return cls(**data)

class WorkflowQueue:
    """Redis-backed workflow job queue with priority support"""
    
    def __init__(self, redis_client: redis.Redis, queue_name: str = "workflow_queue"):
        self.redis = redis_client
        self.queue_name = queue_name
        self.job_prefix = f"{queue_name}:job"
        self.active_jobs_key = f"{queue_name}:active"
        self.scheduled_jobs_key = f"{queue_name}:scheduled"
        self.completed_jobs_key = f"{queue_name}:completed"
        self.failed_jobs_key = f"{queue_name}:failed"
        
        # Priority queues
        self.priority_queues = {
            JobPriority.CRITICAL: f"{queue_name}:critical",
            JobPriority.HIGH: f"{queue_name}:high", 
            JobPriority.NORMAL: f"{queue_name}:normal",
            JobPriority.LOW: f"{queue_name}:low"
        }
    
    async def enqueue_workflow(
        self,
        workflow_id: str,
        user_id: str,
        workflow_data: Dict[str, Any],
        execution_inputs: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Enqueue a workflow for execution"""
        
        job_id = str(uuid.uuid4())
        
        job = WorkflowJob(
            job_id=job_id,
            workflow_id=workflow_id,
            user_id=user_id,
            priority=priority,
            created_at=datetime.utcnow(),
            scheduled_at=scheduled_at,
            metadata=metadata or {}
        )
        
        # Store job data
        job_data = {
            "job": job.to_dict(),
            "workflow_data": workflow_data,
            "execution_inputs": execution_inputs
        }
        
        await self._store_job(job_id, job_data)
        
        if scheduled_at and scheduled_at > datetime.utcnow():
            # Schedule for later execution
            await self._schedule_job(job_id, scheduled_at)
            logger.info(f"Scheduled workflow job {job_id} for {scheduled_at}")
        else:
            # Add to priority queue immediately
            await self._enqueue_job(job_id, priority)
            logger.info(f"Enqueued workflow job {job_id} with priority {priority}")
        
        return job_id
    
    async def dequeue_job(self, timeout: int = 10) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Dequeue the next job for execution (blocking)"""
        
        # Check priority queues in order
        for priority in [JobPriority.CRITICAL, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
            queue_key = self.priority_queues[priority]
            
            # Try to get a job from this priority queue
            job_id = await self._redis_blpop(queue_key, timeout=1)
            
            if job_id:
                job_data = await self._get_job_data(job_id)
                if job_data:
                    # Mark job as active
                    await self._mark_job_active(job_id)
                    await self._update_job_status(job_id, JobStatus.RUNNING)
                    
                    logger.info(f"Dequeued job {job_id} from {priority} queue")
                    return job_id, job_data
        
        return None
    
    async def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark job as completed"""
        
        await self._update_job_status(job_id, JobStatus.COMPLETED, result=result)
        await self._remove_from_active(job_id)
        await self._move_to_completed(job_id)
        
        logger.info(f"Job {job_id} completed successfully")
    
    async def fail_job(self, job_id: str, error_message: str, should_retry: bool = True):
        """Mark job as failed and optionally retry"""
        
        job_data = await self._get_job_data(job_id)
        if not job_data:
            return
        
        job = WorkflowJob.from_dict(job_data["job"])
        job.retry_count += 1
        job.error_message = error_message
        
        if should_retry and job.retry_count <= job.max_retries:
            # Retry with exponential backoff
            delay_seconds = min(300, 2 ** job.retry_count)  # Max 5 minutes
            scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            
            job.status = JobStatus.RETRYING
            job.scheduled_at = scheduled_at
            
            # Update job data
            job_data["job"] = job.to_dict()
            await self._store_job(job_id, job_data)
            
            # Schedule for retry
            await self._schedule_job(job_id, scheduled_at)
            await self._remove_from_active(job_id)
            
            logger.info(f"Job {job_id} scheduled for retry #{job.retry_count} in {delay_seconds}s")
        else:
            # Permanently failed
            await self._update_job_status(job_id, JobStatus.FAILED, error_message=error_message)
            await self._remove_from_active(job_id)
            await self._move_to_failed(job_id)
            
            logger.error(f"Job {job_id} permanently failed after {job.retry_count} retries: {error_message}")
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or scheduled job"""
        
        job_data = await self._get_job_data(job_id)
        if not job_data:
            return False
        
        job = WorkflowJob.from_dict(job_data["job"])
        
        if job.status in [JobStatus.PENDING, JobStatus.RETRYING]:
            # Remove from priority queues
            for queue_key in self.priority_queues.values():
                await self._redis_lrem(queue_key, job_id)
            
            # Remove from scheduled jobs
            await self._redis_zrem(self.scheduled_jobs_key, job_id)
            
            await self._update_job_status(job_id, JobStatus.CANCELLED)
            
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
    
    async def get_job_status(self, job_id: str) -> Optional[WorkflowJob]:
        """Get job status and details"""
        
        job_data = await self._get_job_data(job_id)
        if job_data:
            return WorkflowJob.from_dict(job_data["job"])
        return None
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        
        stats = {}
        
        # Count jobs in each priority queue
        for priority, queue_key in self.priority_queues.items():
            count = await self._redis_llen(queue_key)
            stats[f"pending_{priority.name.lower()}"] = count
        
        # Count active jobs
        stats["active"] = await self._redis_scard(self.active_jobs_key)
        
        # Count scheduled jobs
        stats["scheduled"] = await self._redis_zcard(self.scheduled_jobs_key)
        
        # Count completed/failed jobs (recent)
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        stats["completed_last_hour"] = await self._redis_zcount(
            self.completed_jobs_key, 
            hour_ago.timestamp(), 
            now.timestamp()
        )
        
        stats["failed_last_hour"] = await self._redis_zcount(
            self.failed_jobs_key,
            hour_ago.timestamp(),
            now.timestamp()
        )
        
        return stats
    
    async def process_scheduled_jobs(self):
        """Process jobs scheduled for execution (should be called periodically)"""
        
        now = datetime.utcnow().timestamp()
        
        # Get jobs scheduled for now or earlier
        scheduled_jobs = await self._redis_zrangebyscore(
            self.scheduled_jobs_key, 
            0, 
            now,
            withscores=False
        )
        
        for job_id in scheduled_jobs:
            job_data = await self._get_job_data(job_id)
            if job_data:
                job = WorkflowJob.from_dict(job_data["job"])
                
                # Remove from scheduled and add to appropriate priority queue
                await self._redis_zrem(self.scheduled_jobs_key, job_id)
                await self._enqueue_job(job_id, job.priority)
                await self._update_job_status(job_id, JobStatus.PENDING)
                
                logger.info(f"Moved scheduled job {job_id} to execution queue")
    
    # Redis helper methods
    async def _store_job(self, job_id: str, job_data: Dict[str, Any]):
        """Store job data in Redis"""
        key = f"{self.job_prefix}:{job_id}"
        await self._redis_set(key, json.dumps(job_data, default=str))
        # Set expiration (7 days)
        await self._redis_expire(key, 7 * 24 * 3600)
    
    async def _get_job_data(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job data from Redis"""
        key = f"{self.job_prefix}:{job_id}"
        data = await self._redis_get(key)
        if data:
            return json.loads(data)
        return None
    
    async def _enqueue_job(self, job_id: str, priority: JobPriority):
        """Add job to priority queue"""
        queue_key = self.priority_queues[priority]
        await self._redis_rpush(queue_key, job_id)
    
    async def _schedule_job(self, job_id: str, scheduled_at: datetime):
        """Add job to scheduled jobs sorted set"""
        await self._redis_zadd(self.scheduled_jobs_key, {job_id: scheduled_at.timestamp()})
    
    async def _mark_job_active(self, job_id: str):
        """Mark job as actively running"""
        await self._redis_sadd(self.active_jobs_key, job_id)
    
    async def _remove_from_active(self, job_id: str):
        """Remove job from active set"""
        await self._redis_srem(self.active_jobs_key, job_id)
    
    async def _move_to_completed(self, job_id: str):
        """Move job to completed jobs set with timestamp"""
        timestamp = datetime.utcnow().timestamp()
        await self._redis_zadd(self.completed_jobs_key, {job_id: timestamp})
    
    async def _move_to_failed(self, job_id: str):
        """Move job to failed jobs set with timestamp"""
        timestamp = datetime.utcnow().timestamp()
        await self._redis_zadd(self.failed_jobs_key, {job_id: timestamp})
    
    async def _update_job_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None
    ):
        """Update job status in stored data"""
        job_data = await self._get_job_data(job_id)
        if job_data:
            job = WorkflowJob.from_dict(job_data["job"])
            job.status = status
            
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.utcnow()
            
            if error_message:
                job.error_message = error_message
            if result:
                job.result = result
            
            job_data["job"] = job.to_dict()
            await self._store_job(job_id, job_data)
    
    # Async Redis wrapper methods (adapt based on your Redis client)
    async def _redis_set(self, key: str, value: str):
        return self.redis.set(key, value)
    
    async def _redis_get(self, key: str):
        return self.redis.get(key)
    
    async def _redis_expire(self, key: str, seconds: int):
        return self.redis.expire(key, seconds)
    
    async def _redis_rpush(self, key: str, value: str):
        return self.redis.rpush(key, value)
    
    async def _redis_blpop(self, key: str, timeout: int):
        result = self.redis.blpop(key, timeout=timeout)
        return result[1].decode() if result else None
    
    async def _redis_llen(self, key: str):
        return self.redis.llen(key)
    
    async def _redis_lrem(self, key: str, value: str):
        return self.redis.lrem(key, 0, value)
    
    async def _redis_sadd(self, key: str, value: str):
        return self.redis.sadd(key, value)
    
    async def _redis_srem(self, key: str, value: str):
        return self.redis.srem(key, value)
    
    async def _redis_scard(self, key: str):
        return self.redis.scard(key)
    
    async def _redis_zadd(self, key: str, mapping: Dict[str, float]):
        return self.redis.zadd(key, mapping)
    
    async def _redis_zrem(self, key: str, value: str):
        return self.redis.zrem(key, value)
    
    async def _redis_zcard(self, key: str):
        return self.redis.zcard(key)
    
    async def _redis_zcount(self, key: str, min_score: float, max_score: float):
        return self.redis.zcount(key, min_score, max_score)
    
    async def _redis_zrangebyscore(self, key: str, min_score: float, max_score: float, withscores: bool = True):
        result = self.redis.zrangebyscore(key, min_score, max_score, withscores=withscores)
        if withscores:
            return result
        return [item.decode() for item in result]


class WorkflowWorker:
    """Background worker for processing workflow jobs"""
    
    def __init__(self, queue: WorkflowQueue, execution_engine, worker_id: str = None):
        self.queue = queue
        self.execution_engine = execution_engine
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.current_job_id = None
    
    async def start(self):
        """Start the worker loop"""
        self.running = True
        logger.info(f"Worker {self.worker_id} started")
        
        while self.running:
            try:
                # Check for scheduled jobs first
                await self.queue.process_scheduled_jobs()
                
                # Get next job from queue
                job_result = await self.queue.dequeue_job(timeout=10)
                
                if job_result:
                    job_id, job_data = job_result
                    self.current_job_id = job_id
                    
                    try:
                        # Execute the workflow
                        await self._execute_workflow_job(job_id, job_data)
                    except Exception as e:
                        logger.error(f"Worker {self.worker_id} failed to execute job {job_id}: {str(e)}")
                        await self.queue.fail_job(job_id, str(e))
                    finally:
                        self.current_job_id = None
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id} loop error: {str(e)}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def stop(self):
        """Stop the worker gracefully"""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopping")
    
    async def _execute_workflow_job(self, job_id: str, job_data: Dict[str, Any]):
        """Execute a single workflow job"""
        
        job_info = WorkflowJob.from_dict(job_data["job"])
        workflow_data = job_data["workflow_data"]
        execution_inputs = job_data["execution_inputs"]
        
        logger.info(f"Worker {self.worker_id} executing workflow {job_info.workflow_id}")
        
        try:
            # Execute workflow using the execution engine
            result = await self.execution_engine.execute_workflow(
                nodes=workflow_data.get("nodes", []),
                edges=workflow_data.get("edges", []),
                initial_inputs=execution_inputs,
                workflow_data={},  # Can be expanded
                request=None  # Would need to mock or handle differently
            )
            
            # Mark job as completed
            await self.queue.complete_job(job_id, result)
            
        except Exception as e:
            error_message = f"Workflow execution failed: {str(e)}\n{traceback.format_exc()}"
            await self.queue.fail_job(job_id, error_message)
            raise 
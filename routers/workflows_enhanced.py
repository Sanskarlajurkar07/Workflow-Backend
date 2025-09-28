from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks, WebSocket, WebSocketDisconnect
from models.workflow import Workflow, WorkflowCreate, WorkflowExecutionRequest, WorkflowExecutionResponse, NodeResult
from models.user import User
from routers.auth import get_current_user_optional_token
from database import get_workflow_collection
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
import asyncio
import logging
import json

# Import our new services
from services.parallel_execution_engine import ParallelExecutionEngine, WorkflowValidator
from services.execution_monitor import execution_monitor, ExecutionEventType
from services.workflow_queue import WorkflowQueue, JobPriority, JobStatus

logger = logging.getLogger("workflow_api")

router = APIRouter()

# Initialize services (these would be dependency injected in production)
execution_engine = ParallelExecutionEngine(max_concurrent_nodes=5)
workflow_queue = None  # Will be initialized with Redis client

@router.on_event("startup")
async def setup_workflow_services():
    global workflow_queue
    # Initialize workflow queue with Redis client from app
    # workflow_queue = WorkflowQueue(app.redis, "production_workflows")
    pass

# ENHANCED EXECUTION ENDPOINTS

@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow_sync(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Execute a workflow synchronously with parallel processing"""
    logger.info(f"Starting synchronous workflow execution: {workflow_id}")
    
    # Find the workflow
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Validate workflow structure
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    validation_result = WorkflowValidator.validate_workflow(nodes, edges)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Workflow validation failed: {validation_result['errors']}"
        )
    
    # Start monitoring
    await execution_monitor.start_workflow_monitoring(
        workflow_id, str(current_user.id), workflow
    )
    
    start_time = time.time()
    
    try:
        # Execute with parallel engine
        result = await execution_engine.execute_workflow(
            nodes=nodes,
            edges=edges,
            initial_inputs=execution_request.inputs,
            workflow_data={"workflow_id": workflow_id, "user_id": str(current_user.id)},
            request=request
        )
        
        execution_time = time.time() - start_time
        
        # Log completion
        await execution_monitor.workflow_completed(
            workflow_id, result, execution_time
        )
        
        # Record execution in database
        executions_collection = request.app.mongodb.workflow_executions
        execution_log = {
            "workflow_id": workflow_id,
            "user_id": str(current_user.id),
            "started_at": datetime.utcnow() - timedelta(seconds=execution_time),
            "completed_at": datetime.utcnow(),
            "inputs": execution_request.dict(),
            "results": result,
            "status": "completed",
            "execution_time": execution_time,
            "execution_stats": result.get("execution_stats", {})
        }
        await executions_collection.insert_one(execution_log)
        
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=str(execution_log.get("_id")),
            status="completed",
            results=result.get("node_outputs", {}),
            node_results=result.get("node_results", {}),
            execution_time=execution_time,
            execution_stats=result.get("execution_stats")
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_message = str(e)
        
        # Log failure
        await execution_monitor.workflow_failed(
            workflow_id, error_message, execution_time
        )
        
        # Record failure in database
        executions_collection = request.app.mongodb.workflow_executions
        execution_log = {
            "workflow_id": workflow_id,
            "user_id": str(current_user.id),
            "started_at": datetime.utcnow() - timedelta(seconds=execution_time),
            "completed_at": datetime.utcnow(),
            "inputs": execution_request.dict(),
            "status": "failed",
            "error": error_message,
            "execution_time": execution_time
        }
        await executions_collection.insert_one(execution_log)
        
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {error_message}")

@router.post("/{workflow_id}/execute-async")
async def execute_workflow_async(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    request: Request,
    priority: JobPriority = JobPriority.NORMAL,
    scheduled_at: Optional[datetime] = None,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Queue a workflow for asynchronous execution"""
    
    if not workflow_queue:
        raise HTTPException(status_code=503, detail="Workflow queue not available")
    
    # Find the workflow
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Validate workflow structure
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    validation_result = WorkflowValidator.validate_workflow(nodes, edges)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Workflow validation failed: {validation_result['errors']}"
        )
    
    # Enqueue the workflow
    job_id = await workflow_queue.enqueue_workflow(
        workflow_id=workflow_id,
        user_id=str(current_user.id),
        workflow_data=workflow,
        execution_inputs=execution_request.inputs,
        priority=priority,
        scheduled_at=scheduled_at,
        metadata={
            "workflow_name": workflow.get("name", "Unnamed Workflow"),
            "node_count": len(nodes)
        }
    )
    
    return {
        "job_id": job_id,
        "workflow_id": workflow_id,
        "status": "queued",
        "priority": priority,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "message": "Workflow queued for execution"
    }

@router.get("/{workflow_id}/execution-status")
async def get_execution_status(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get real-time execution status"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get status from execution monitor
    status = execution_monitor.get_execution_status(workflow_id)
    
    if status:
        return status
    else:
        # Check recent executions in database
        executions_collection = request.app.mongodb.workflow_executions
        recent_execution = await executions_collection.find_one(
            {"workflow_id": workflow_id, "user_id": str(current_user.id)},
            sort=[("started_at", -1)]
        )
        
        if recent_execution:
            return {
                "workflow_id": workflow_id,
                "status": recent_execution.get("status", "unknown"),
                "started_at": recent_execution.get("started_at"),
                "completed_at": recent_execution.get("completed_at"),
                "execution_time": recent_execution.get("execution_time")
            }
        else:
            return {
                "workflow_id": workflow_id,
                "status": "not_executed",
                "message": "No execution history found"
            }

@router.get("/{workflow_id}/execution-history")
async def get_execution_history(
    workflow_id: str,
    request: Request,
    limit: int = 50,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get execution event history"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get event history from monitor
    events = execution_monitor.get_execution_history(workflow_id)
    
    # Also get database execution logs
    executions_collection = request.app.mongodb.workflow_executions
    db_executions = await executions_collection.find(
        {"workflow_id": workflow_id, "user_id": str(current_user.id)},
        limit=limit,
        sort=[("started_at", -1)]
    ).to_list(limit)
    
    return {
        "workflow_id": workflow_id,
        "real_time_events": events[-limit:] if events else [],
        "execution_logs": db_executions
    }

# WORKFLOW CONTROL ENDPOINTS

@router.post("/{workflow_id}/pause")
async def pause_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Pause an active workflow execution"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is currently executing
    status = execution_monitor.get_execution_status(workflow_id)
    if not status or status["status"] != "running":
        raise HTTPException(status_code=400, detail="Workflow is not currently executing")
    
    # Pause execution
    await execution_monitor.pause_execution(workflow_id)
    
    return {"message": "Workflow execution paused", "workflow_id": workflow_id}

@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Resume a paused workflow execution"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is currently paused
    status = execution_monitor.get_execution_status(workflow_id)
    if not status or status["status"] != "paused":
        raise HTTPException(status_code=400, detail="Workflow is not currently paused")
    
    # Resume execution
    await execution_monitor.resume_execution(workflow_id)
    
    return {"message": "Workflow execution resumed", "workflow_id": workflow_id}

@router.post("/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Cancel an active or queued workflow execution"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    cancelled = False
    
    # Try to cancel in queue first
    if workflow_queue:
        # Get all jobs for this workflow (in case multiple are queued)
        # This would need a method to find jobs by workflow_id
        # cancelled = await workflow_queue.cancel_workflow_jobs(workflow_id)
        pass
    
    # Cancel active execution
    status = execution_monitor.get_execution_status(workflow_id)
    if status and status["status"] in ["running", "paused"]:
        await execution_monitor.cancel_execution(workflow_id)
        cancelled = True
    
    if cancelled:
        return {"message": "Workflow execution cancelled", "workflow_id": workflow_id}
    else:
        raise HTTPException(status_code=400, detail="No active workflow execution to cancel")

# JOB QUEUE MANAGEMENT ENDPOINTS

@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get job status from queue"""
    
    if not workflow_queue:
        raise HTTPException(status_code=503, detail="Workflow queue not available")
    
    job = await workflow_queue.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify job belongs to current user
    if job.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return job.to_dict()

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Cancel a queued job"""
    
    if not workflow_queue:
        raise HTTPException(status_code=503, detail="Workflow queue not available")
    
    job = await workflow_queue.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify job belongs to current user
    if job.user_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    cancelled = await workflow_queue.cancel_job(job_id)
    
    if cancelled:
        return {"message": "Job cancelled", "job_id": job_id}
    else:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")

@router.get("/queue/stats")
async def get_queue_stats(
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get workflow queue statistics (admin only)"""
    
    if not workflow_queue:
        raise HTTPException(status_code=503, detail="Workflow queue not available")
    
    # Add admin check here if needed
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    stats = await workflow_queue.get_queue_stats()
    return stats

# REAL-TIME WEBSOCKET ENDPOINT

@router.websocket("/{workflow_id}/ws")
async def workflow_websocket(
    websocket: WebSocket,
    workflow_id: str,
    token: str = None  # JWT token for authentication
):
    """WebSocket endpoint for real-time workflow execution updates"""
    
    try:
        # Authenticate user (simplified - in production use proper JWT validation)
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        # Mock user validation - replace with actual JWT decode
        user_id = "user_from_token"  # Extract from JWT
        
        # Connect to execution monitor
        await execution_monitor.connection_manager.connect(
            websocket, workflow_id, user_id
        )
        
        # Send current status if available
        current_status = execution_monitor.get_execution_status(workflow_id)
        if current_status:
            await websocket.send_text(json.dumps({
                "type": "status_update",
                "data": current_status
            }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for client messages (e.g., ping/pong for keepalive)
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        execution_monitor.connection_manager.disconnect(websocket)

# WORKFLOW VALIDATION ENDPOINT

@router.post("/{workflow_id}/validate")
async def validate_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Validate workflow structure and configuration"""
    
    # Find the workflow
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Validate workflow structure
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    validation_result = WorkflowValidator.validate_workflow(nodes, edges)
    
    return {
        "workflow_id": workflow_id,
        "validation_result": validation_result,
        "node_count": len(nodes),
        "edge_count": len(edges)
    }

# DRY RUN ENDPOINT

@router.post("/{workflow_id}/dry-run")
async def dry_run_workflow(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Perform a dry run of the workflow without executing external operations"""
    
    # Find the workflow
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Validate workflow structure
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    validation_result = WorkflowValidator.validate_workflow(nodes, edges)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Workflow validation failed: {validation_result['errors']}"
        )
    
    # Build execution order to show planned execution
    try:
        engine = ParallelExecutionEngine()
        dependency_graph = engine._build_dependency_graph(nodes, edges)
        
        # Simulate execution order analysis
        execution_plan = {
            "total_nodes": len(nodes),
            "dependency_graph": {node_id: list(deps) for node_id, deps in dependency_graph.items()},
            "validation_result": validation_result,
            "estimated_parallel_batches": len([
                node for node in nodes 
                if not dependency_graph.get(node["id"], set())
            ]),
            "inputs_provided": execution_request.inputs,
            "dry_run": True
        }
        
        return execution_plan
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dry run analysis failed: {str(e)}") 
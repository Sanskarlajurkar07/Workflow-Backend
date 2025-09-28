import asyncio
import json
import logging
from typing import Dict, List, Any, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import uuid
from enum import Enum

logger = logging.getLogger("workflow_api")

class ExecutionEventType(str, Enum):
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_PROGRESS = "node_progress"
    EXECUTION_PAUSED = "execution_paused"
    EXECUTION_RESUMED = "execution_resumed"
    EXECUTION_CANCELLED = "execution_cancelled"

class ExecutionEvent:
    def __init__(self, event_type: ExecutionEventType, workflow_id: str, **kwargs):
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.timestamp = datetime.utcnow().isoformat()
        self.event_id = str(uuid.uuid4())
        self.data = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "data": self.data
        }

class ConnectionManager:
    """Manages WebSocket connections for real-time execution monitoring"""
    
    def __init__(self):
        # workflow_id -> set of websockets
        self.workflow_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> set of websockets  
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> {workflow_id, user_id}
        self.connection_metadata: Dict[WebSocket, Dict[str, str]] = {}
    
    async def connect(self, websocket: WebSocket, workflow_id: str, user_id: str):
        """Connect a client to workflow execution updates"""
        await websocket.accept()
        
        # Add to workflow connections
        if workflow_id not in self.workflow_connections:
            self.workflow_connections[workflow_id] = set()
        self.workflow_connections[workflow_id].add(websocket)
        
        # Add to user connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "workflow_id": workflow_id,
            "user_id": user_id
        }
        
        logger.info(f"WebSocket connected for workflow {workflow_id}, user {user_id}")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a client"""
        if websocket in self.connection_metadata:
            metadata = self.connection_metadata[websocket]
            workflow_id = metadata["workflow_id"]
            user_id = metadata["user_id"]
            
            # Remove from workflow connections
            if workflow_id in self.workflow_connections:
                self.workflow_connections[workflow_id].discard(websocket)
                if not self.workflow_connections[workflow_id]:
                    del self.workflow_connections[workflow_id]
            
            # Remove from user connections
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove metadata
            del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected for workflow {workflow_id}, user {user_id}")
    
    async def send_to_workflow(self, workflow_id: str, event: ExecutionEvent):
        """Send event to all clients monitoring this workflow"""
        if workflow_id in self.workflow_connections:
            message = json.dumps(event.to_dict())
            disconnected = []
            
            for websocket in self.workflow_connections[workflow_id]:
                try:
                    await websocket.send_text(message)
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for websocket in disconnected:
                self.disconnect(websocket)
    
    async def send_to_user(self, user_id: str, event: ExecutionEvent):
        """Send event to all connections for a specific user"""
        if user_id in self.user_connections:
            message = json.dumps(event.to_dict())
            disconnected = []
            
            for websocket in self.user_connections[user_id]:
                try:
                    await websocket.send_text(message)
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected websockets
            for websocket in disconnected:
                self.disconnect(websocket)

class ExecutionMonitor:
    """Real-time workflow execution monitoring system"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.execution_history: Dict[str, List[ExecutionEvent]] = {}
    
    async def start_workflow_monitoring(self, workflow_id: str, user_id: str, workflow_data: Dict[str, Any]):
        """Initialize monitoring for a new workflow execution"""
        
        self.active_executions[workflow_id] = {
            "user_id": user_id,
            "status": "running",
            "started_at": datetime.utcnow(),
            "nodes": workflow_data.get("nodes", []),
            "edges": workflow_data.get("edges", []),
            "completed_nodes": set(),
            "failed_nodes": set(),
            "current_executing": set()
        }
        
        event = ExecutionEvent(
            ExecutionEventType.WORKFLOW_STARTED,
            workflow_id,
            user_id=user_id,
            total_nodes=len(workflow_data.get("nodes", [])),
            workflow_name=workflow_data.get("name", "Unnamed Workflow")
        )
        
        await self._emit_event(workflow_id, event)
    
    async def node_started(self, workflow_id: str, node_id: str, node_type: str, inputs: Dict[str, Any]):
        """Record node execution start"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["current_executing"].add(node_id)
        
        event = ExecutionEvent(
            ExecutionEventType.NODE_STARTED,
            workflow_id,
            node_id=node_id,
            node_type=node_type,
            inputs=self._sanitize_inputs(inputs)  # Remove sensitive data
        )
        
        await self._emit_event(workflow_id, event)
    
    async def node_completed(self, workflow_id: str, node_id: str, result: Dict[str, Any], execution_time: float):
        """Record successful node completion"""
        
        if workflow_id in self.active_executions:
            execution = self.active_executions[workflow_id]
            execution["current_executing"].discard(node_id)
            execution["completed_nodes"].add(node_id)
        
        event = ExecutionEvent(
            ExecutionEventType.NODE_COMPLETED,
            workflow_id,
            node_id=node_id,
            execution_time=execution_time,
            output=self._sanitize_output(result)  # Remove sensitive data
        )
        
        await self._emit_event(workflow_id, event)
    
    async def node_failed(self, workflow_id: str, node_id: str, error: str, execution_time: float):
        """Record node execution failure"""
        
        if workflow_id in self.active_executions:
            execution = self.active_executions[workflow_id]
            execution["current_executing"].discard(node_id)
            execution["failed_nodes"].add(node_id)
        
        event = ExecutionEvent(
            ExecutionEventType.NODE_FAILED,
            workflow_id,
            node_id=node_id,
            error=error,
            execution_time=execution_time
        )
        
        await self._emit_event(workflow_id, event)
    
    async def node_progress(self, workflow_id: str, node_id: str, progress: int, message: str = ""):
        """Update node execution progress (for long-running nodes)"""
        
        event = ExecutionEvent(
            ExecutionEventType.NODE_PROGRESS,
            workflow_id,
            node_id=node_id,
            progress=progress,
            message=message
        )
        
        await self._emit_event(workflow_id, event)
    
    async def workflow_completed(self, workflow_id: str, results: Dict[str, Any], execution_time: float):
        """Record successful workflow completion"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["status"] = "completed"
            self.active_executions[workflow_id]["completed_at"] = datetime.utcnow()
        
        event = ExecutionEvent(
            ExecutionEventType.WORKFLOW_COMPLETED,
            workflow_id,
            total_execution_time=execution_time,
            results=self._sanitize_output(results)
        )
        
        await self._emit_event(workflow_id, event)
    
    async def workflow_failed(self, workflow_id: str, error: str, execution_time: float):
        """Record workflow execution failure"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["status"] = "failed"
            self.active_executions[workflow_id]["completed_at"] = datetime.utcnow()
        
        event = ExecutionEvent(
            ExecutionEventType.WORKFLOW_FAILED,
            workflow_id,
            error=error,
            total_execution_time=execution_time
        )
        
        await self._emit_event(workflow_id, event)
    
    async def pause_execution(self, workflow_id: str):
        """Pause workflow execution"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["status"] = "paused"
        
        event = ExecutionEvent(
            ExecutionEventType.EXECUTION_PAUSED,
            workflow_id
        )
        
        await self._emit_event(workflow_id, event)
    
    async def resume_execution(self, workflow_id: str):
        """Resume workflow execution"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["status"] = "running"
        
        event = ExecutionEvent(
            ExecutionEventType.EXECUTION_RESUMED,
            workflow_id
        )
        
        await self._emit_event(workflow_id, event)
    
    async def cancel_execution(self, workflow_id: str):
        """Cancel workflow execution"""
        
        if workflow_id in self.active_executions:
            self.active_executions[workflow_id]["status"] = "cancelled"
            self.active_executions[workflow_id]["completed_at"] = datetime.utcnow()
        
        event = ExecutionEvent(
            ExecutionEventType.EXECUTION_CANCELLED,
            workflow_id
        )
        
        await self._emit_event(workflow_id, event)
    
    def get_execution_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current execution status"""
        
        if workflow_id not in self.active_executions:
            return None
        
        execution = self.active_executions[workflow_id]
        total_nodes = len(execution["nodes"])
        completed_nodes = len(execution["completed_nodes"])
        failed_nodes = len(execution["failed_nodes"])
        executing_nodes = len(execution["current_executing"])
        
        return {
            "workflow_id": workflow_id,
            "status": execution["status"],
            "started_at": execution["started_at"].isoformat(),
            "progress": {
                "total_nodes": total_nodes,
                "completed_nodes": completed_nodes,
                "failed_nodes": failed_nodes,
                "executing_nodes": executing_nodes,
                "percentage": (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
            },
            "current_executing": list(execution["current_executing"])
        }
    
    def get_execution_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get execution event history"""
        
        if workflow_id not in self.execution_history:
            return []
        
        return [event.to_dict() for event in self.execution_history[workflow_id]]
    
    async def _emit_event(self, workflow_id: str, event: ExecutionEvent):
        """Emit event to connected clients and store in history"""
        
        # Store in history
        if workflow_id not in self.execution_history:
            self.execution_history[workflow_id] = []
        self.execution_history[workflow_id].append(event)
        
        # Limit history size (keep last 1000 events)
        if len(self.execution_history[workflow_id]) > 1000:
            self.execution_history[workflow_id] = self.execution_history[workflow_id][-1000:]
        
        # Send to connected clients
        await self.connection_manager.send_to_workflow(workflow_id, event)
        
        logger.info(f"Emitted event {event.event_type} for workflow {workflow_id}")
    
    def _sanitize_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from inputs before sending to clients"""
        
        sanitized = {}
        for key, value in inputs.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                sanitized[key] = "***HIDDEN***"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[truncated]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from outputs before sending to clients"""
        
        if not isinstance(output, dict):
            return output
        
        sanitized = {}
        for key, value in output.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                sanitized[key] = "***HIDDEN***"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[truncated]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_output(value)
            else:
                sanitized[key] = value
        
        return sanitized

# Global monitor instance
execution_monitor = ExecutionMonitor() 
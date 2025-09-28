from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, float]
    data: Dict[str, Any]

class Edge(BaseModel):
    id: str
    source: str
    target: str
    data: Optional[Dict[str, Any]] = None

class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: List[Node]
    edges: List[Edge]

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowUpdate(WorkflowBase):
    pass

class Workflow(WorkflowBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# New models for workflow execution
class InputValue(BaseModel):
    value: Any
    type: str = "Text"

class WorkflowExecutionRequest(BaseModel):
    inputs: Dict[str, InputValue]
    mode: str = "standard"  # standard, chatbot, or voice

class NodeResult(BaseModel):
    output: Any
    type: str = "Text"
    execution_time: float = 0.0
    status: str = "success"
    error: Optional[str] = None
    node_id: Optional[str] = None
    node_name: Optional[str] = None

class WorkflowExecutionResponse(BaseModel):
    outputs: Dict[str, Dict[str, Any]]
    execution_time: float
    status: str = "success"
    error: Optional[str] = None
    execution_path: List[str] = []  # List of node IDs in execution order
    execution_id: Optional[str] = None
    node_results: Optional[Dict[str, Dict[str, Any]]] = None
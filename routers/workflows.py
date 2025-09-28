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
from routers.nodes import (
    handle_openai_query, 
    handle_anthropic_query,
    handle_gemini_query,
    handle_cohere_query,
    handle_perplexity_query,
    handle_xai_query,
    handle_aws_query,
    handle_azure_query
)
import re
import json
import httpx
from models.integrations import IntegrationType, GitHubActionType, AirtableActionType, NotionActionType
import os
import pytz
import calendar
import decimal
# Import our new node handlers
from new_node_handlers import (
    handle_chat_memory_node,
    handle_data_collector_node,
    handle_chat_file_reader_node
)

logger = logging.getLogger("workflow_api")

router = APIRouter()

@router.get("/", response_model=List[Workflow])
async def list_workflows(request: Request, current_user: User = Depends(get_current_user_optional_token)):
    workflow_collection = await get_workflow_collection(request)
    workflows = await workflow_collection.find({"user_id": str(current_user.id)}).to_list(None)
    return [Workflow(**workflow, id=str(workflow["_id"])) for workflow in workflows]

@router.post("/", response_model=Workflow, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: Request,
    workflow: WorkflowCreate,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    workflow_data = {
        **workflow.dict(),
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = await workflow_collection.insert_one(workflow_data)
    created_workflow = await workflow_collection.find_one({"_id": result.inserted_id})
    return Workflow(**created_workflow, id=str(created_workflow["_id"]))

@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return Workflow(**workflow, id=str(workflow["_id"]))

@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowCreate,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    update_data = {
        **workflow_update.dict(),
        "updated_at": datetime.utcnow()
    }
    
    await workflow_collection.update_one(
        {"_id": ObjectId(workflow_id)},
        {"$set": update_data}
    )
    
    updated_workflow = await workflow_collection.find_one({"_id": ObjectId(workflow_id)})
    return Workflow(**updated_workflow, id=str(updated_workflow["_id"]))

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    result = await workflow_collection.delete_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")

@router.post("/{workflow_id}/clone", response_model=Workflow)
async def clone_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow_data = {
        **workflow,
        "_id": ObjectId(),
        "name": f"{workflow['name']} (Copy)",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await workflow_collection.insert_one(workflow_data)
    created_workflow = await workflow_collection.find_one({"_id": result.inserted_id})
    return Workflow(**created_workflow, id=str(created_workflow["_id"]))

@router.get("/{workflow_id}/export")
async def export_workflow(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Remove internal fields before export
    workflow.pop("_id", None)
    workflow.pop("user_id", None)
    return workflow

@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Execute a workflow with the given inputs - FIXED VERSION"""
    logger.info(f"Starting workflow execution: {workflow_id}")
    
    # Start execution timer
    start_time = time.time()
    
    # Find the workflow
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        logger.warning(f"Workflow not found: {workflow_id}")
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Extract nodes and edges
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    logger.info(f"Executing workflow with {len(nodes)} nodes and {len(edges)} edges")
    
    # Record execution in the database
    execution_log = {
        "workflow_id": workflow_id,
        "user_id": str(current_user.id),
        "started_at": datetime.utcnow(),
        "inputs": execution_request.dict(),
        "status": "in_progress"
    }
    
    executions_collection = request.app.mongodb.workflow_executions
    execution_result = await executions_collection.insert_one(execution_log)
    execution_id = str(execution_result.inserted_id)
    logger.info(f"Created execution log: {execution_id}")
    
    try:
        # Calculate execution order using topological sort
        if not nodes:
            logger.warning("No nodes found in workflow")
            raise HTTPException(status_code=400, detail="Workflow has no nodes to execute")
        
        execution_order = calculate_execution_order(nodes, edges)
        execution_path = [node["id"] for node in execution_order]
        logger.info(f"Execution order: {execution_path}")
        
        # Initialize workflow state
        node_outputs = {}
        node_results = {}
        workflow_variables = {}
        
        # Set up request context for node execution
        request.workflow_variables = workflow_variables
        request.node_outputs = node_outputs
        
        # Execute each node in order
        for i, node in enumerate(execution_order):
            node_id = node["id"]
            node_type = node["type"]
            
            logger.info(f"Executing node {i+1}/{len(execution_order)}: {node_id} (type: {node_type})")
            node_start_time = time.time()
            
            try:
                # Get inputs for this node
                inputs = get_node_inputs(node_id, edges, node_outputs, execution_request.inputs, nodes)
                logger.info(f"Node {node_id} inputs: {list(inputs.keys())}")
                
                # Execute the node
                result = await execute_workflow_node(
                    node, inputs, workflow_variables, request, str(current_user.id)
                )
                
                # Process the result
                if result is None:
                    logger.warning(f"Node {node_id} returned None result")
                    result = NodeResult(output="", status="completed", execution_time=0)
                
                # Handle different result types
                if hasattr(result, 'output'):
                    # It's a NodeResult object
                    node_output = result.output
                    node_status = getattr(result, 'status', 'completed')
                    node_exec_time = getattr(result, 'execution_time', time.time() - node_start_time)
                elif isinstance(result, dict):
                    # It's a dictionary result
                    node_output = result
                    node_status = 'completed'
                    node_exec_time = time.time() - node_start_time
                else:
                    # It's a raw value
                    node_output = result
                    node_status = 'completed'
                    node_exec_time = time.time() - node_start_time
                
                # Normalize node output for consistent variable access
                from variable_processor import normalize_node_output
                normalized_output = normalize_node_output(node_output, node_type)
                
                # Store outputs and results
                node_outputs[node_id] = normalized_output
                node_results[node_id] = {
                    "status": node_status,
                    "execution_time": node_exec_time,
                    "output": normalized_output,
                    "node_type": node_type
                }
                
                logger.info(f"Node {node_id} completed successfully in {node_exec_time:.3f}s")
                logger.info(f"Node {node_id} normalized output keys: {list(normalized_output.keys()) if isinstance(normalized_output, dict) else 'not dict'}")
                logger.debug(f"Node {node_id} output: {str(normalized_output)[:200]}...")
                
            except Exception as e:
                node_execution_time = time.time() - node_start_time
                error_message = str(e)
                logger.error(f"Error executing node {node_id}: {error_message}", exc_info=True)
                
                # Record node error but continue execution
                node_results[node_id] = {
                    "status": "error",
                    "execution_time": node_execution_time,
                    "error": error_message,
                    "output": None,
                    "node_type": node_type
                }
                
                # Set empty output for failed nodes
                node_outputs[node_id] = None
        
        # Calculate total execution time
        total_execution_time = time.time() - start_time
        
        # Prepare final results
        execution_stats = {
            "total_nodes": len(execution_order),
            "successful_nodes": len([r for r in node_results.values() if r["status"] not in ["error", "failed"]]),
            "failed_nodes": len([r for r in node_results.values() if r["status"] in ["error", "failed"]]),
            "execution_path": execution_path,
            "total_execution_time": total_execution_time
        }
        
        # Determine overall status
        has_errors = any(r["status"] in ["error", "failed"] for r in node_results.values())
        overall_status = "completed_with_errors" if has_errors else "completed"
        
        # Update execution log with results
        await executions_collection.update_one(
            {"_id": execution_result.inserted_id},
            {
                "$set": {
                    "completed_at": datetime.utcnow(),
                    "status": overall_status,
                    "results": node_outputs,
                    "node_results": node_results,
                    "execution_time": total_execution_time,
                    "execution_stats": execution_stats
                }
            }
        )
        
        logger.info(f"Workflow execution completed in {total_execution_time:.2f}s")
        logger.info(f"Results: {execution_stats['successful_nodes']} successful, {execution_stats['failed_nodes']} failed")
        
        # Return the execution response
        return WorkflowExecutionResponse(
            execution_id=execution_id,
            outputs=node_outputs,
            node_results=node_results,
            execution_time=total_execution_time,
            execution_path=execution_path,
            status=overall_status,
            error=None
        )
        
    except Exception as e:
        total_execution_time = time.time() - start_time
        error_message = str(e)
        logger.error(f"Workflow execution failed: {error_message}", exc_info=True)
        
        # Get partial results if available
        partial_outputs = getattr(locals().get('node_outputs'), 'copy', lambda: {})() if 'node_outputs' in locals() else {}
        partial_results = getattr(locals().get('node_results'), 'copy', lambda: {})() if 'node_results' in locals() else {}
        
        # Update execution log with error
        await executions_collection.update_one(
            {"_id": execution_result.inserted_id},
            {
                "$set": {
                    "completed_at": datetime.utcnow(),
                    "status": "failed",
                    "error": error_message,
                    "results": partial_outputs,
                    "node_results": partial_results,
                    "execution_time": total_execution_time
                }
            }
        )
        
        # Return error response
        return WorkflowExecutionResponse(
            execution_id=execution_id,
            outputs=partial_outputs,
            node_results=partial_results,
            execution_time=total_execution_time,
            execution_path=[],
            status="failed",
            error=error_message
        )

@router.post("/{workflow_id}/fix_input_types")
async def fix_input_types(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Fix the input node types in a workflow"""
    logger.info(f"Fixing input types for workflow: {workflow_id}")
    
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Extract nodes 
    nodes = workflow.get("nodes", [])
    
    # Find input nodes and ensure they have a type
    updated = False
    fixed_nodes = 0
    
    for i, node in enumerate(nodes):
        if node.get("type") == "input":
            node_id = node.get("id", f"unknown-{i}")
            logger.info(f"Processing input node: {node_id}")
            
            # Ensure the node has a data.params object
            if "data" not in node:
                node["data"] = {}
                updated = True
                logger.info(f"Added missing data object to node {node_id}")
                
            if "params" not in node["data"]:
                node["data"]["params"] = {}
                updated = True
                logger.info(f"Added missing params object to node {node_id}")
                
            # If no type is set, default to Text
            if "type" not in node["data"]["params"] or not node["data"]["params"]["type"]:
                node["data"]["params"]["type"] = "Text"
                updated = True
                fixed_nodes += 1
                logger.info(f"Set default type 'Text' for input node {node_id}")
                
            # Make sure nodeName is set properly
            if "nodeName" not in node["data"]["params"] or not node["data"]["params"]["nodeName"]:
                # Extract node index
                node_index = node_id.split('-')[1] if '-' in node_id else '0'
                node["data"]["params"]["nodeName"] = f"Input {node_index}"
                updated = True
                logger.info(f"Set default nodeName for input node {node_id}")
    
    # If any updates were made, save the workflow
    if updated:
        await workflow_collection.update_one(
            {"_id": ObjectId(workflow_id)},
            {"$set": {"nodes": nodes, "updated_at": datetime.utcnow()}}
        )
        logger.info(f"Fixed {fixed_nodes} input nodes in workflow {workflow_id}")
        return {"message": f"Fixed {fixed_nodes} input node types", "updated": True, "fixed_count": fixed_nodes}
    
    logger.info(f"No input node fixes needed for workflow {workflow_id}")
    return {"message": "No updates needed", "updated": False, "fixed_count": 0}

# Helper functions for workflow execution

def calculate_execution_order(nodes, edges):
    """Calculate the topological sort of nodes for execution order"""
    # Create a graph representation
    graph = {node["id"]: [] for node in nodes}
    
    # Add edges to the graph
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source in graph:
            graph[source].append(target)
    
    # Perform topological sort
    visited = set()
    temp_visited = set()
    order = []
    
    def visit(node_id):
        if node_id in temp_visited:
            raise ValueError(f"Circular dependency detected at node {node_id}")
        if node_id in visited:
            return
        
        temp_visited.add(node_id)
        
        # Visit neighbors
        for neighbor in graph.get(node_id, []):
            visit(neighbor)
        
        temp_visited.remove(node_id)
        visited.add(node_id)
        
        # Get the node and add to order
        node = next((n for n in nodes if n["id"] == node_id), None)
        if node:
            order.append(node)
    
    # Start with input nodes or nodes with no incoming edges
    start_nodes = [
        node["id"] for node in nodes 
        if node["type"] == "input" or not any(edge["target"] == node["id"] for edge in edges)
    ]
    
    # If no start nodes, start with any node
    if not start_nodes and nodes:
        start_nodes = [nodes[0]["id"]]
    
    # Visit all nodes
    for node_id in start_nodes:
        if node_id not in visited:
            visit(node_id)
    
    # Make sure all nodes are visited
    remaining = [node for node in nodes if node["id"] not in visited]
    order.extend(remaining)
    
    # Reverse the order to get the correct execution flow (input first, output last)
    return list(reversed(order))

def get_node_inputs(node_id, edges, node_outputs, initial_inputs, nodes):
    """Get the inputs for a node from connected nodes"""
    inputs = {}
    
    # Find all edges that target this node
    incoming_edges = [edge for edge in edges if edge["target"] == node_id]
    
    # Process each incoming edge
    for edge in incoming_edges:
        source_id = edge["source"]
        if source_id in node_outputs:
            output = node_outputs[source_id]
            # Get the right output field based on the edge
            output_field = edge.get("sourceHandle", "output")
            input_field = edge.get("targetHandle", "input")
            
            # Handle special case where .text is used instead of .output
            if output_field == "text" and "output" in output:
                output_field = "output"
            
            if output_field in output:
                inputs[input_field] = output[output_field]
    
    # For input nodes, use the initial inputs
    if not inputs and node_id.startswith("input"):
        # Extract the node index from the id (input_0, input_1, etc.)
        node_parts = node_id.split('-')
        node_index = node_parts[1] if len(node_parts) > 1 else '0'
        
        # Try multiple input key patterns
        possible_keys = [
            f"input_{node_index}",  # input_1 format
            f"input{node_index}",   # input1 format  
            "input",                # generic input format
            node_id                 # exact node ID
        ]
        
        input_value = None
        used_key = None
        
        # Find the first matching key
        for key in possible_keys:
            if key in initial_inputs:
                input_value = initial_inputs[key]
                used_key = key
                break
        
        # If we found an input, use it
        if input_value is not None:
            # Handle the InputValue model or direct value
            if hasattr(input_value, 'value'):
                inputs["input"] = input_value.value
            else:
                inputs["input"] = input_value
                
            # Add type information that might be needed by the node
            node_info = next((n for n in nodes if n["id"] == node_id), None)
            if node_info:
                input_type = node_info.get("data", {}).get("params", {}).get("type", "Text")
                inputs["type"] = input_type
    
    return inputs

async def execute_workflow_node(node: Dict[str, Any], inputs: Dict[str, Any], workflow_data: Dict[str, Any], request: Request, user_id: str) -> NodeResult:
    """Execute a specific node in the workflow and return its result"""
    # Use the node_handlers module for node execution
    from node_handlers import handle_node
    
    # Create workflow data that persists between nodes if it doesn't exist
    if not hasattr(request, 'workflow_variables'):
        request.workflow_variables = {}
        
    workflow_variables = request.workflow_variables
    
    # Extract node information
    node_id = node["id"]
    node_type = node["type"]
    node_data = node.get("data", {})
    
    # Use the handle_node function from node_handlers
    return await handle_node(node_id, node_type, node_data, inputs, workflow_variables, request)

def find_execution_path(start_node_id, all_nodes, edges):
    """
    Find all nodes in a path starting from a given node.
    This is used to determine the execution path after a condition node.
    
    Args:
        start_node_id: ID of the node to start from
        all_nodes: List of all nodes in the workflow
        edges: List of all edges in the workflow
        
    Returns:
        List of nodes in the execution path
    """
    # Find the start node
    start_node = next((n for n in all_nodes if n["id"] == start_node_id), None)
    if not start_node:
        return []
    
    # Create a graph representation
    graph = {node["id"]: [] for node in all_nodes}
    
    # Add edges to the graph
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source in graph:
            graph[source].append(target)
    
    # BFS to find all descendants
    visited = set()
    queue = [start_node_id]
    ordered_nodes = []
    
    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
            
        visited.add(current_id)
        current_node = next((n for n in all_nodes if n["id"] == current_id), None)
        if current_node:
            ordered_nodes.append(current_node)
            
        # Add all unvisited children to the queue
        for child_id in graph.get(current_id, []):
            if child_id not in visited:
                queue.append(child_id)
    
    # Convert to a more sensible execution order
    # Start with the given node
    result = [start_node]
    
    # Find node dependencies and sort them
    visited = set([start_node_id])
    
    def add_dependencies(node_id):
        # Add all dependents of this node in the right order
        children = [n["id"] for n in all_nodes if n["id"] in graph.get(node_id, [])]
        for child_id in children:
            if child_id not in visited:
                child_node = next((n for n in all_nodes if n["id"] == child_id), None)
                if child_node:
                    result.append(child_node)
                    visited.add(child_id)
                    add_dependencies(child_id)
    
    # Recursively add all dependencies
    add_dependencies(start_node_id)
    
    return result

def get_dependent_nodes(node_id, edges, remaining_nodes):
    """
    Get nodes that depend on the given node for their inputs.
    
    Args:
        node_id: ID of the node to check dependencies for
        edges: List of all edges in the workflow
        remaining_nodes: List of remaining nodes to check
        
    Returns:
        List of nodes that depend on the given node
    """
    dependent_nodes = []
    
    # Find all edges where this node is the source
    outgoing_edges = [edge for edge in edges if edge["source"] == node_id]
    
    # For each outgoing edge, check if the target is in remaining nodes
    for edge in outgoing_edges:
        target_id = edge["target"]
        target_node = next((node for node in remaining_nodes if node["id"] == target_id), None)
        if target_node:
            dependent_nodes.append(target_node)
    
    return dependent_nodes

@router.post("/{workflow_id}/validate")
async def validate_workflow_structure(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Validate workflow structure and configuration before execution"""
    
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
    
    try:
        from services.parallel_execution_engine import WorkflowValidator
        validation_result = WorkflowValidator.validate_workflow(nodes, edges)
    except ImportError:
        # Basic validation fallback
        validation_result = {
            "valid": len(nodes) > 0,
            "errors": [] if len(nodes) > 0 else ["No nodes found in workflow"],
            "warnings": []
        }
    
    return {
        "workflow_id": workflow_id,
        "validation_result": validation_result,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "workflow_name": workflow.get("name", "Unnamed Workflow")
    }

@router.get("/{workflow_id}/execution-status")
async def get_workflow_execution_status(
    workflow_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get real-time execution status for a workflow"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    try:
        # Try to get status from execution monitor
        from services.execution_monitor import execution_monitor
        status = execution_monitor.get_execution_status(workflow_id)
        
        if status:
            return status
    except ImportError:
        pass
    
    # Fallback to database lookup
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
            "execution_time": recent_execution.get("execution_time"),
            "execution_stats": recent_execution.get("execution_stats")
        }
    else:
        return {
            "workflow_id": workflow_id,
            "status": "not_executed",
            "message": "No execution history found"
        }

@router.get("/{workflow_id}/execution-history")
async def get_workflow_execution_history(
    workflow_id: str,
    request: Request,
    limit: int = 10,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get execution history for a workflow"""
    
    # Check if workflow belongs to user
    workflow_collection = await get_workflow_collection(request)
    workflow = await workflow_collection.find_one({
        "_id": ObjectId(workflow_id),
        "user_id": str(current_user.id)
    })
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get execution history from database
    executions_collection = request.app.mongodb.workflow_executions
    executions = await executions_collection.find(
        {"workflow_id": workflow_id, "user_id": str(current_user.id)},
        limit=limit,
        sort=[("started_at", -1)]
    ).to_list(limit)
    
    # Try to get real-time events if available
    real_time_events = []
    try:
        from services.execution_monitor import execution_monitor
        real_time_events = execution_monitor.get_execution_history(workflow_id)
    except ImportError:
        pass
    
    return {
        "workflow_id": workflow_id,
        "execution_history": executions,
        "real_time_events": real_time_events[-limit:] if real_time_events else [],
        "total_executions": len(executions)
    }

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
    
    try:
        from services.parallel_execution_engine import WorkflowValidator, ParallelExecutionEngine
        
        validation_result = WorkflowValidator.validate_workflow(nodes, edges)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Workflow validation failed: {validation_result['errors']}"
            )
        
        # Analyze execution plan
        engine = ParallelExecutionEngine()
        dependency_graph = engine._build_dependency_graph(nodes, edges)
        
        # Find nodes that can run in parallel (no dependencies)
        parallel_nodes = [
            node for node in nodes 
            if not dependency_graph.get(node["id"], set())
        ]
        
        execution_plan = {
            "workflow_id": workflow_id,
            "total_nodes": len(nodes),
            "dependency_graph": {node_id: list(deps) for node_id, deps in dependency_graph.items()},
            "validation_result": validation_result,
            "parallel_start_nodes": len(parallel_nodes),
            "estimated_parallel_batches": max(1, len(nodes) - len(parallel_nodes)),
            "inputs_provided": execution_request.inputs,
            "dry_run": True,
            "estimated_execution_time": f"{len(nodes) * 2}s (estimated)"
        }
        
        return execution_plan
        
    except ImportError:
        # Basic fallback analysis
        return {
            "workflow_id": workflow_id,
            "total_nodes": len(nodes),
            "inputs_provided": execution_request.inputs,
            "dry_run": True,
            "message": "Enhanced analysis not available - basic validation passed",
            "basic_validation": {"valid": len(nodes) > 0, "node_count": len(nodes)}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dry run analysis failed: {str(e)}")

from fastapi import WebSocket, WebSocketDisconnect
import json

@router.websocket("/{workflow_id}/ws")
async def workflow_websocket_endpoint(
    websocket: WebSocket,
    workflow_id: str,
    token: str = None  # JWT token for authentication
):
    """WebSocket endpoint for real-time workflow execution updates"""
    
    try:
        await websocket.accept()
        
        # Basic authentication check (in production, validate JWT properly)
        if not token:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Authentication required"
            }))
            await websocket.close()
            return
        
        # Mock user validation - replace with actual JWT decode
        user_id = "user_from_token"  # Extract from JWT in production
        
        try:
            # Try to connect to execution monitor
            from services.execution_monitor import execution_monitor
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
            else:
                await websocket.send_text(json.dumps({
                    "type": "connected",
                    "message": f"Connected to workflow {workflow_id}",
                    "workflow_id": workflow_id
                }))
        except ImportError:
            # Fallback if monitoring service not available
            await websocket.send_text(json.dumps({
                "type": "connected",
                "message": f"Connected to workflow {workflow_id} (basic mode)",
                "workflow_id": workflow_id
            }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif data.get("type") == "get_status":
                    # Send current status on request
                    try:
                        from services.execution_monitor import execution_monitor
                        status = execution_monitor.get_execution_status(workflow_id)
                        await websocket.send_text(json.dumps({
                            "type": "status_response",
                            "data": status
                        }))
                    except ImportError:
                        await websocket.send_text(json.dumps({
                            "type": "status_response",
                            "data": {"status": "monitoring_unavailable"}
                        }))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
                break
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        try:
            from services.execution_monitor import execution_monitor
            execution_monitor.connection_manager.disconnect(websocket)
        except ImportError:
            pass
                    
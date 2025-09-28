from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
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
    """Execute a workflow with the given inputs"""
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
    
    # Log input node types for debugging
    input_nodes = [node for node in nodes if node.get("type") == "input"]
    for node in input_nodes:
        node_id = node.get("id", "unknown")
        node_type = node.get("data", {}).get("params", {}).get("type", "unknown")
        logger.info(f"Input node {node_id} has type: {node_type}")
        
    # Log incoming input values
    logger.info(f"Execution inputs: {execution_request.inputs}")
    
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
        conn.execute("EXPLAIN " + sql_query)
    except sqlite3.Error as e:
        validation_result = {"valid": False, "errors": [str(e)]}
        # Calculate initial execution order (topological sort)
        if not nodes:
            logger.warning("No nodes found in workflow")
            execution_order = []
            execution_path = []
        else:
            execution_order = calculate_execution_order(nodes, edges)
            execution_path = [node["id"] for node in execution_order]
            
        # If execution_order is empty but we have nodes, add them all in a sensible order
        if not execution_order and nodes:
            logger.warning("No execution order determined, falling back to basic order")
            # Prioritize inputs first, then processing nodes, then outputs
            input_nodes = [node for node in nodes if node["type"] == "input"]
            output_nodes = [node for node in nodes if node["type"] == "output"]
            other_nodes = [node for node in nodes if node["type"] not in ["input", "output"]]
            
            execution_order = input_nodes + other_nodes + output_nodes
            execution_path = [node["id"] for node in execution_order]
        
        logger.info(f"Initial execution order: {execution_path}")
        
        # Initialize node outputs, results and detailed execution stats
        node_outputs = {}
        results = {}
        node_results = {}
        actual_execution_path = []
        
        # Process each node in order, with dynamic path determination
        i = 0
        while i < len(execution_order):
            node = execution_order[i]
            node_id = node["id"]
            node_type = node["type"]
            node_data = node.get("data", {})
            
            logger.info(f"Executing node {i+1}/{len(execution_order)}: {node_id} ({node_type})")
            
            # Track the actual execution path
            actual_execution_path.append(node_id)
            
            # Get inputs for this node
            node_inputs = get_node_inputs(node_id, edges, node_outputs, execution_request.inputs, nodes)
            
            # Record node execution start
            node_start_time = time.time()
            
            try:
                # Execute the node based on its type
                result = await execute_workflow_node(node, node_inputs, workflow, request, str(current_user.id))
                
                # Store the output and node result
                node_outputs[node_id] = result.output
                node_results[node_id] = {
                    "status": result.status,
                    "execution_time": result.execution_time,
                    "output": result.output
                }
                
                # Log successful node execution
                logger.info(f"Node {node_id} executed successfully in {result.execution_time:.3f}s")
                
                # If this is an output node, add to results
                if node_type == "output":
                    output_key = f"output_{node_id.split('-')[1] if '-' in node_id else '0'}"
                    results[output_key] = result
                
                # For condition nodes, we need to determine which path to take next
                if node_type == "condition" and isinstance(result.output, dict):
                    selected_path_index = result.output.get("selected_path")
                    
                    if selected_path_index is not None:
                        logger.info(f"Condition node {node_id} selected path: {selected_path_index}")
                        
                        # Find outgoing edges for this condition node
                        outgoing_edges = [e for e in edges if e["source"] == node_id]
                        
                        # Identify the correct edge based on the selected path
                        if outgoing_edges and len(outgoing_edges) > selected_path_index:
                            # Sort edges by handle ID if available, or by target ID
                            sorted_edges = sorted(outgoing_edges, 
                                key=lambda e: (e.get("sourceHandle", "") or f"path_{outgoing_edges.index(e)}"))
                            
                            if selected_path_index < len(sorted_edges):
                                selected_edge = sorted_edges[selected_path_index]
                                target_id = selected_edge["target"]
                                
                                logger.info(f"Following path to node {target_id}")
                                
                                # Find the target node and all its descendants
                                next_nodes = find_execution_path(target_id, nodes, edges)
                                
                                if next_nodes:
                                    # Create a new execution order from this point forward
                                    remaining = [n for n in execution_order[i+1:] if n["id"] in [node["id"] for node in next_nodes]]
                                    execution_order = execution_order[:i+1] + next_nodes + [n for n in remaining if n not in next_nodes]
                                    
                                    # Update the execution path
                                    execution_path = [node["id"] for node in execution_order]
                                    logger.info(f"Updated execution order: {execution_path}")
                
                # Move to the next node
                i += 1
            
            except Exception as e:
                # Log node execution error
                node_execution_time = time.time() - node_start_time
                error_message = str(e)
                logger.error(f"Error executing node {node_id}: {error_message}")
                
                # Record node error
                node_results[node_id] = {
                    "status": "error",
                    "execution_time": node_execution_time,
                    "error": error_message
                }
                
                # Add error to results if it's an output node
                if node_type == "output":
                    output_key = f"output_{node_id.split('-')[1] if '-' in node_id else '0'}"
                    results[output_key] = NodeResult(
                        output=None,
                        type="null",
                        execution_time=node_execution_time,
                        status="error",
                        error=error_message,
                        node_id=node_id,
                        node_name=node_data.get("name", "Output")
                    )
                
                # If it's not the last node, we should consider stopping execution
                if i < len(execution_order) - 1:
                    # Check if this node's output is required for any downstream nodes
                    next_nodes = get_dependent_nodes(node_id, edges, execution_order[i+1:])
                    if next_nodes:
                        # If there are dependent nodes, we can't continue
                        logger.warning(f"Stopping execution after node {node_id} due to error")
                        break
                    else:
                        # If no dependent nodes, we can continue execution
                        i += 1
                else:
                    # This is the last node, so we're done
                    break
        
        # Calculate total execution time
        total_execution_time = time.time() - start_time
        logger.info(f"Workflow executed in {total_execution_time:.3f}s, status: {'success' if i >= len(execution_order) else 'partial'}")
        
        # Update execution log in database
        await executions_collection.update_one(
            {"_id": ObjectId(execution_id)},
            {"$set": {
                "completed_at": datetime.utcnow(),
                "execution_time": total_execution_time,
                "status": "completed" if i >= len(execution_order) else "partial",
                "outputs": {k: v.dict() for k, v in results.items()},
                "node_results": node_results,
                "execution_path": actual_execution_path
            }}
        )
        
        # Return the results
        return WorkflowExecutionResponse(
            execution_id=execution_id,
            outputs=results,
            execution_time=total_execution_time,
            status="success" if i >= len(execution_order) else "partial",
            execution_path=actual_execution_path,
            node_results=node_results
        )
        
    except Exception as e:
        # Log the error
        logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
        
        # Update execution log with error
        await executions_collection.update_one(
            {"_id": ObjectId(execution_id)},
            {"$set": {
                "completed_at": datetime.utcnow(),
                "execution_time": time.time() - start_time,
                "status": "error",
                "error": str(e),
                "node_results": node_results
            }}
        )
        
        # Return error response
        return WorkflowExecutionResponse(
            execution_id=execution_id,
            outputs={},
            execution_time=time.time() - start_time,
            status="error",
            error=str(e),
            node_results=node_results
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
        
        # Create a unique input key based on node ID
        input_key = f"input_{node_index}"
        
        # Only use the input if it specifically exists in the initial inputs
        if input_key in initial_inputs:
            # Ensure we're getting the value correctly
            input_value = initial_inputs[input_key]
            
            # Log the input being used
            print(f"Using input value for {node_id}: {input_key}")
            
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
    node_type = node.get("type")
    node_id = node.get("id")
    node_data = node.get("data", {})
    
    # Start timing node execution
    start_time = time.time()
    
    try:
        # Execute node based on its type
        if node_type == "input":
            # Input node just passes through the workflow inputs
            result = NodeResult(
                output=inputs,
                type="object",
                execution_time=time.time() - start_time,
                status="success",
                node_id=node_id,
                node_name=node_data.get("name", "Input")
            )
            
        elif node_type == "output":
            # Output node for final workflow results
            result = NodeResult(
                output=inputs.get("input", None),
                type="object",
                execution_time=time.time() - start_time,
                status="success",
                node_id=node_id,
                node_name=node_data.get("name", "Output")
            )
            
        # Merge Node
        elif node_type == "merge":
            logger.info(f"Executing merge node {node_id}")
            
            # Get merge function
            merge_function = node_data.get("params", {}).get("function", "Pick First")
            input_paths = node_data.get("params", {}).get("paths", [])
            data_type = node_data.get("params", {}).get("type", "Text")
            join_delimiter = node_data.get("params", {}).get("joinDelimiter", " ")
            
            # Default paths if none provided
            if not input_paths:
                input_paths = ["input"]
                logger.warning(f"Merge node {node_id} had no input paths, defaulting to ['input']")
            
            # Get input values
            input_value = inputs.get("input")
            logger.info(f"Merge node input: {type(input_value)}")
            
            # Parse input value if it's a string that looks like JSON
            if isinstance(input_value, str):
                try:
                    if (input_value.startswith('{') and input_value.endswith('}')) or \
                       (input_value.startswith('[') and input_value.endswith(']')):
                        parsed_value = json.loads(input_value)
                        input_value = parsed_value
                        logger.info(f"Parsed JSON string input to object: {type(input_value)}")
                except json.JSONDecodeError:
                    # Keep as string if not valid JSON
                    pass
            
            # Apply the merge function
            result_value = None
            
            try:
                if merge_function == "Pick First":
                    # Use the first non-null value
                    if isinstance(input_value, dict):
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                result_value = value
                                logger.info(f"Merge node picked first value from path '{path}'")
                                break
                        
                        # If no path found, use input as is
                        if result_value is None:
                            result_value = input_value
                            logger.warning(f"No valid path found in merge node, using input as is")
                    else:
                        result_value = input_value
                
                elif merge_function == "Join All":
                    # Join all values from all paths
                    if isinstance(input_value, dict):
                        # Collect values from each path
                        values = []
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                values.append(value)
                        
                        # Join based on data type
                        if data_type == "Text":
                            # Join strings with custom delimiter
                            result_value = join_delimiter.join(str(v) for v in values if v is not None)
                        elif data_type in ["Integer", "Float", "Number"]:
                            # Sum numbers
                            try:
                                result_value = sum(float(v) for v in values if v is not None)
                                if data_type == "Integer":
                                    result_value = int(result_value)
                            except (ValueError, TypeError):
                                # Fall back to joining as strings if conversion fails
                                result_value = join_delimiter.join(str(v) for v in values if v is not None)
                                logger.warning(f"Could not sum values as numbers, joined as strings instead")
                        elif data_type == "JSON" or data_type == "Any":
                            # For JSON/Any, return an array of all values
                            result_value = values
                        else:
                            # Default to first value for other types
                            result_value = values[0] if values else None
                    else:
                        result_value = input_value
                
                elif merge_function == "Concatenate Arrays":
                    # Concatenate arrays from multiple paths
                    if isinstance(input_value, dict):
                        result_array = []
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                if isinstance(value, list):
                                    result_array.extend(value)
                                else:
                                    # Treat non-array values as single items
                                    result_array.append(value)
                    
                        result_value = result_array
                    else:
                        # If input is not a dict, treat it as a single item in an array
                        result_value = [input_value] if input_value is not None else []
                
                elif merge_function == "Merge Objects":
                    # Deep merge objects from multiple paths
                    if isinstance(input_value, dict):
                        result_obj = {}
                        
                        # Helper function for deep merge
                        def deep_merge(target, source):
                            for key, value in source.items():
                                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                                    # If both values are dicts, merge them recursively
                                    deep_merge(target[key], value)
                                elif key in target and isinstance(target[key], list) and isinstance(value, list):
                                    # If both values are lists, concatenate them
                                    target[key].extend(value)
                                else:
                                    # Otherwise, source overwrites target
                                    target[key] = value
                        
                        # Process each path in order (later paths override earlier ones)
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            path_parts = path.split('.')
                            
                            # Navigate to the nested value
                            for i, key in enumerate(path_parts[:-1]):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            # Extract the value and merge into result
                            if path_found and isinstance(value, dict) and path_parts[-1] in value:
                                path_value = value[path_parts[-1]]
                                if isinstance(path_value, dict):
                                    deep_merge(result_obj, path_value)
                                elif isinstance(path_value, (str, int, float, bool, list)):
                                    # For non-dict values, use the path name as key
                                    result_obj[path_parts[-1]] = path_value
                            elif path_found and len(path_parts) == 1 and path in input_value:
                                # Direct root-level path
                                path_value = input_value[path]
                                if isinstance(path_value, dict):
                                    deep_merge(result_obj, path_value)
                                elif isinstance(path_value, (str, int, float, bool, list)):
                                    result_obj[path] = path_value
                        
                        result_value = result_obj
                    else:
                        # If input is not a dict, return it as is
                        result_value = input_value
                
                elif merge_function == "Average":
                    # Calculate average of numeric values
                    if isinstance(input_value, dict):
                        values = []
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                # Try to convert to number
                                try:
                                    if isinstance(value, (int, float)):
                                        values.append(value)
                                    else:
                                        values.append(float(value))
                                except (ValueError, TypeError):
                                    logger.warning(f"Could not convert value '{value}' to number for averaging")
                        
                        # Calculate average if we have values
                        if values:
                            result_value = sum(values) / len(values)
                            # Convert to int if data_type is Integer
                            if data_type == "Integer":
                                result_value = int(result_value)
                        else:
                            result_value = 0
                    else:
                        # Try to convert input to number
                        try:
                            if isinstance(input_value, (int, float)):
                                result_value = input_value
                            else:
                                result_value = float(input_value)
                                if data_type == "Integer":
                                    result_value = int(result_value)
                        except (ValueError, TypeError):
                            result_value = 0
                            logger.warning(f"Could not convert input to number for averaging")
                
                elif merge_function == "Min":
                    # Find minimum value
                    if isinstance(input_value, dict):
                        values = []
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                # Try to convert to number
                                try:
                                    if isinstance(value, (int, float)):
                                        values.append(value)
                                    else:
                                        values.append(float(value))
                                except (ValueError, TypeError):
                                    logger.warning(f"Could not convert value '{value}' to number for min")
                        
                        # Find minimum if we have values
                        if values:
                            result_value = min(values)
                            # Convert to int if data_type is Integer
                            if data_type == "Integer":
                                result_value = int(result_value)
                        else:
                            result_value = None
                    else:
                        result_value = input_value
                
                elif merge_function == "Max":
                    # Find maximum value
                    if isinstance(input_value, dict):
                        values = []
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            
                            for key in path.split('.'):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            if path_found and value is not None:
                                # Try to convert to number
                                try:
                                    if isinstance(value, (int, float)):
                                        values.append(value)
                                    else:
                                        values.append(float(value))
                                except (ValueError, TypeError):
                                    logger.warning(f"Could not convert value '{value}' to number for max")
                        
                        # Find maximum if we have values
                        if values:
                            result_value = max(values)
                            # Convert to int if data_type is Integer
                            if data_type == "Integer":
                                result_value = int(result_value)
                        else:
                            result_value = None
                    else:
                        result_value = input_value
                
                elif merge_function == "Create Object":
                    # Create a new object with keys from path names and values from those paths
                    result_obj = {}
                    
                    if isinstance(input_value, dict):
                        for path in input_paths:
                            # Support dot notation for nested paths
                            value = input_value
                            path_found = True
                            path_parts = path.split('.')
                            
                            # Navigate to the nested value
                            for key in path_parts:
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    path_found = False
                                    break
                            
                            # Use the last part of the path as the key
                            if path_found:
                                key_name = path_parts[-1]
                                result_obj[key_name] = value
                    
                    result_value = result_obj
                
                else:
                    # Unknown merge function, fallback to input
                    logger.warning(f"Unknown merge function: {merge_function}, falling back to input")
                    result_value = input_value
            
            except Exception as e:
                logger.error(f"Error in merge node: {str(e)}", exc_info=True)
                result_value = {
                    "error": f"Merge error: {str(e)}",
                    "input": input_value
                }
            
            # Set a default value if result is None
            if result_value is None:
                if data_type == "Text":
                    result_value = ""
                elif data_type in ["Integer", "Float", "Number"]:
                    result_value = 0
                elif data_type == "Boolean":
                    result_value = False
                elif data_type in ["Array", "List"]:
                    result_value = []
                elif data_type == "Object":
                    result_value = {}
                else:
                    result_value = None
            
            # Create the node result
            result = NodeResult(
                output=result_value,
                type=data_type.lower(),
                execution_time=time.time() - start_time,
                status="success",
                node_id=node_id,
                node_name=node_data.get("name", "Merge")
            )
        
        # Time Node
        elif node_type == "time":
            logger.info(f"Executing time node {node_id}")
            
            # Get timezone from node data
            timezone_str = node_data.get("params", {}).get("timezone", "UTC")
            time_operation = node_data.get("params", {}).get("operation", "current_time")
            custom_format = node_data.get("params", {}).get("customFormat", "")
            input_date = node_data.get("params", {}).get("inputDate", "")
            
            # Get modification parameters (for arithmetic operations)
            modify_value = node_data.get("params", {}).get("modifyValue", 0)
            try:
                modify_value = int(modify_value)
            except (ValueError, TypeError):
                modify_value = 0
                logger.warning(f"Invalid modify value: {modify_value}, using 0")
            
            modify_unit = node_data.get("params", {}).get("modifyUnit", "days")
            
            # Get input override if available
            input_value = inputs.get("input")
            if input_value:
                if isinstance(input_value, dict):
                    # Override parameters from input if available
                    if "timezone" in input_value:
                        timezone_str = input_value["timezone"]
                    if "operation" in input_value:
                        time_operation = input_value["operation"]
                    if "inputDate" in input_value:
                        input_date = input_value["inputDate"]
                    if "modifyValue" in input_value:
                        try:
                            modify_value = int(input_value["modifyValue"])
                        except (ValueError, TypeError):
                            pass
                    if "modifyUnit" in input_value:
                        modify_unit = input_value["modifyUnit"]
                    if "customFormat" in input_value:
                        custom_format = input_value["customFormat"]
                elif isinstance(input_value, str) and input_value:
                    # If input is a string, use it as input date
                    input_date = input_value
            
            try:
                # Validate timezone
                try:
                    tz = pytz.timezone(timezone_str)
                except pytz.exceptions.UnknownTimeZoneError:
                    logger.warning(f"Unknown timezone: {timezone_str}, falling back to UTC")
                    tz = pytz.timezone("UTC")
                    timezone_str = "UTC"
                
                # Initialize the time based on operation
                if time_operation == "parse_input" and input_date:
                    # Try to parse the input date
                    current_time = None
                    
                    if isinstance(input_date, datetime.datetime):
                        # If already a datetime object, use it
                        current_time = input_date
                    elif isinstance(input_date, (int, float)):
                        # Assume timestamp
                        current_time = datetime.datetime.fromtimestamp(input_date, tz=pytz.UTC)
                    elif isinstance(input_date, str):
                        # Try common date formats with timezone awareness
                        for fmt in [
                            "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f%z",
                            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                            "%Y-%m-%d", "%Y/%m/%d", 
                            "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y",
                            "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"
                        ]:
                            try:
                                parsed_time = datetime.datetime.strptime(input_date, fmt)
                                # If the format doesn't include timezone, assume UTC
                                if not hasattr(parsed_time, 'tzinfo') or parsed_time.tzinfo is None:
                                    parsed_time = parsed_time.replace(tzinfo=pytz.UTC)
                                current_time = parsed_time
                                break
                            except ValueError:
                                continue
                    
                    if current_time is None:
                        raise ValueError(f"Could not parse date from input: {input_date}")
                    
                    # Convert to the specified timezone
                    current_time = current_time.astimezone(tz)
                else:
                    # Get current time in the specified timezone
                    current_time = datetime.datetime.now(tz)
                
                # Apply time operations if specified
                if time_operation == "add_time" and modify_value:
                    if modify_unit == "seconds":
                        current_time = current_time + datetime.timedelta(seconds=modify_value)
                    elif modify_unit == "minutes":
                        current_time = current_time + datetime.timedelta(minutes=modify_value)
                    elif modify_unit == "hours":
                        current_time = current_time + datetime.timedelta(hours=modify_value)
                    elif modify_unit == "days":
                        current_time = current_time + datetime.timedelta(days=modify_value)
                    elif modify_unit == "weeks":
                        current_time = current_time + datetime.timedelta(weeks=modify_value)
                    elif modify_unit == "months":
                        # Handle month addition with proper month boundary handling
                        year = current_time.year
                        month = current_time.month + modify_value
                        
                        # Adjust year if month overflow
                        year += (month - 1) // 12
                        month = ((month - 1) % 12) + 1
                        
                        # Handle day boundary for months with fewer days
                        day = min(current_time.day, calendar.monthrange(year, month)[1])
                        
                        current_time = current_time.replace(year=year, month=month, day=day)
                    elif modify_unit == "years":
                        # Handle leap year edge case (Feb 29)
                        year = current_time.year + modify_value
                        month = current_time.month
                        day = current_time.day
                        
                        # Adjust February 29 in non-leap years
                        if month == 2 and day == 29 and not calendar.isleap(year):
                            day = 28
                        
                        current_time = current_time.replace(year=year, day=day)
                    elif modify_unit == "business_days":
                        # Skip weekends when adding business days
                        remaining_days = modify_value
                        current_day = current_time
                        
                        while remaining_days > 0:
                            current_day += datetime.timedelta(days=1)
                            # Skip weekends (5 = Saturday, 6 = Sunday)
                            if current_day.weekday() < 5:
                                remaining_days -= 1
                        
                        current_time = current_day
                
                elif time_operation == "subtract_time" and modify_value:
                    if modify_unit == "seconds":
                        current_time = current_time - datetime.timedelta(seconds=modify_value)
                    elif modify_unit == "minutes":
                        current_time = current_time - datetime.timedelta(minutes=modify_value)
                    elif modify_unit == "hours":
                        current_time = current_time - datetime.timedelta(hours=modify_value)
                    elif modify_unit == "days":
                        current_time = current_time - datetime.timedelta(days=modify_value)
                    elif modify_unit == "weeks":
                        current_time = current_time - datetime.timedelta(weeks=modify_value)
                    elif modify_unit == "months":
                        # Handle month subtraction with proper month boundary handling
                        year = current_time.year
                        month = current_time.month - modify_value
                        
                        # Adjust year if month underflow
                        year += month // 12
                        month = ((month % 12) + 12) % 12
                        if month == 0:
                            month = 12
                        
                        # Handle day boundary for months with fewer days
                        day = min(current_time.day, calendar.monthrange(year, month)[1])
                        
                        current_time = current_time.replace(year=year, month=month, day=day)
                    elif modify_unit == "years":
                        # Handle leap year edge case (Feb 29)
                        year = current_time.year - modify_value
                        month = current_time.month
                        day = current_time.day
                        
                        # Adjust February 29 in non-leap years
                        if month == 2 and day == 29 and not calendar.isleap(year):
                            day = 28
                        
                        current_time = current_time.replace(year=year, day=day)
                    elif modify_unit == "business_days":
                        # Skip weekends when subtracting business days
                        remaining_days = modify_value
                        current_day = current_time
                        
                        while remaining_days > 0:
                            current_day -= datetime.timedelta(days=1)
                            # Skip weekends (5 = Saturday, 6 = Sunday)
                            if current_day.weekday() < 5:
                                remaining_days -= 1
                        
                        current_time = current_day
                
                elif time_operation == "start_of":
                    # Get start of period (day, week, month, year)
                    if modify_unit == "day":
                        current_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif modify_unit == "week":
                        # Start of week (Monday)
                        days_to_monday = current_time.weekday()
                        current_time = (current_time - datetime.timedelta(days=days_to_monday)).replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                    elif modify_unit == "month":
                        current_time = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    elif modify_unit == "quarter":
                        # Start of quarter (Jan 1, Apr 1, Jul 1, Oct 1)
                        quarter_month = ((current_time.month - 1) // 3) * 3 + 1
                        current_time = current_time.replace(
                            month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0
                        )
                    elif modify_unit == "year":
                        current_time = current_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                
                elif time_operation == "end_of":
                    # Get end of period (day, week, month, year)
                    if modify_unit == "day":
                        current_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                    elif modify_unit == "week":
                        # End of week (Sunday)
                        days_to_sunday = 6 - current_time.weekday()
                        current_time = (current_time + datetime.timedelta(days=days_to_sunday)).replace(
                            hour=23, minute=59, second=59, microsecond=999999
                        )
                    elif modify_unit == "month":
                        # Last day of month
                        last_day = calendar.monthrange(current_time.year, current_time.month)[1]
                        current_time = current_time.replace(
                            day=last_day, hour=23, minute=59, second=59, microsecond=999999
                        )
                    elif modify_unit == "quarter":
                        # End of quarter (Mar 31, Jun 30, Sep 30, Dec 31)
                        quarter = (current_time.month - 1) // 3
                        end_month = (quarter * 3) + 3
                        
                        # If it's the 4th quarter, it ends on Dec 31
                        if end_month == 12:
                            last_day = 31
                        else:
                            # Otherwise, it's the last day of Mar, Jun, or Sep
                            last_day = calendar.monthrange(current_time.year, end_month)[1]
                        
                        current_time = current_time.replace(
                            month=end_month, day=last_day, hour=23, minute=59, second=59, microsecond=999999
                        )
                    elif modify_unit == "year":
                        current_time = current_time.replace(
                            month=12, day=31, hour=23, minute=59, second=59, microsecond=999999
                        )
                
                elif time_operation == "next_weekday":
                    # Find the next occurrence of the specified weekday
                    # modify_unit should be a number from 0-6 (0=Monday, 6=Sunday)
                    try:
                        target_weekday = int(modify_unit)
                        if target_weekday < 0 or target_weekday > 6:
                            raise ValueError("Weekday must be between 0 and 6")
                        
                        # Calculate days until the next target weekday
                        days_ahead = target_weekday - current_time.weekday()
                        if days_ahead <= 0:  # Target is today or earlier in the week
                            days_ahead += 7
                        
                        current_time = current_time + datetime.timedelta(days=days_ahead)
                        current_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        logger.warning(f"Invalid weekday: {modify_unit}, expected 0-6")
                
                elif time_operation == "previous_weekday":
                    # Find the previous occurrence of the specified weekday
                    # modify_unit should be a number from 0-6 (0=Monday, 6=Sunday)
                    try:
                        target_weekday = int(modify_unit)
                        if target_weekday < 0 or target_weekday > 6:
                            raise ValueError("Weekday must be between 0 and 6")
                        
                        # Calculate days since the previous target weekday
                        days_back = current_time.weekday() - target_weekday
                        if days_back <= 0:  # Target is today or later in the week
                            days_back += 7
                        
                        current_time = current_time - datetime.timedelta(days=days_back)
                        current_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        logger.warning(f"Invalid weekday: {modify_unit}, expected 0-6")
                
                # Format the time
                custom_formatted = ""
                if custom_format:
                    try:
                        custom_formatted = current_time.strftime(custom_format)
                    except ValueError as e:
                        logger.warning(f"Invalid date format: {custom_format}. Error: {str(e)}")
                        custom_formatted = "Invalid format"
                
                # Build comprehensive time information
                formatted_time = {
                    "iso": current_time.isoformat(),
                    "iso8601": current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    "rfc2822": current_time.strftime("%a, %d %b %Y %H:%M:%S %z"),
                    "timestamp": current_time.timestamp(),
                    "timestamp_ms": int(current_time.timestamp() * 1000),
                    "year": current_time.year,
                    "month": current_time.month,
                    "month_name": current_time.strftime("%B"),
                    "month_abbr": current_time.strftime("%b"),
                    "day": current_time.day,
                    "day_of_week": current_time.weekday(),  # 0=Monday, 6=Sunday
                    "day_name": current_time.strftime("%A"),
                    "day_abbr": current_time.strftime("%a"),
                    "day_of_year": int(current_time.strftime("%j")),
                    "week_of_year": int(current_time.strftime("%W")),
                    "hour": current_time.hour,
                    "hour_12": int(current_time.strftime("%I")),
                    "minute": current_time.minute,
                    "second": current_time.second,
                    "microsecond": current_time.microsecond,
                    "am_pm": current_time.strftime("%p"),
                    "timezone": timezone_str,
                    "timezone_offset": current_time.strftime("%z"),
                    "formatted": current_time.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
                    "human_readable": current_time.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z"),
                    "custom_formatted": custom_formatted,
                    "unix_timestamp": int(current_time.timestamp()),
                    "is_dst": bool(current_time.dst()),
                    "utc_offset": current_time.utcoffset().total_seconds() / 3600 if current_time.utcoffset() else 0,
                    "is_weekend": current_time.weekday() >= 5,  # 5=Saturday, 6=Sunday
                    "quarter": ((current_time.month - 1) // 3) + 1,
                    "days_in_month": calendar.monthrange(current_time.year, current_time.month)[1],
                    "is_leap_year": calendar.isleap(current_time.year)
                }
                
                # Add relative time descriptions
                now = datetime.datetime.now(tz)
                delta = current_time - now
                days_diff = delta.days
                
                if days_diff == 0:
                    if abs(delta.total_seconds()) < 60:
                        relative_time = "just now"
                    elif delta.total_seconds() < 0:
                        mins = int(abs(delta.total_seconds()) / 60)
                        relative_time = f"{mins} minute{'s' if mins != 1 else ''} ago"
                    else:
                        mins = int(delta.total_seconds() / 60)
                        relative_time = f"in {mins} minute{'s' if mins != 1 else ''}"
                elif days_diff == -1:
                    relative_time = "yesterday"
                elif days_diff == 1:
                    relative_time = "tomorrow"
                elif -7 <= days_diff < 0:
                    relative_time = f"{abs(days_diff)} day{'s' if abs(days_diff) != 1 else ''} ago"
                elif 0 < days_diff <= 7:
                    relative_time = f"in {days_diff} day{'s' if days_diff != 1 else ''}"
                elif -30 <= days_diff < -7:
                    weeks = abs(days_diff) // 7
                    relative_time = f"{weeks} week{'s' if weeks != 1 else ''} ago"
                elif 7 < days_diff <= 30:
                    weeks = days_diff // 7
                    relative_time = f"in {weeks} week{'s' if weeks != 1 else ''}"
                elif -365 <= days_diff < -30:
                    months = abs(days_diff) // 30
                    relative_time = f"{months} month{'s' if months != 1 else ''} ago"
                elif 30 < days_diff <= 365:
                    months = days_diff // 30
                    relative_time = f"in {months} month{'s' if months != 1 else ''}"
                elif days_diff < -365:
                    years = abs(days_diff) // 365
                    relative_time = f"{years} year{'s' if years != 1 else ''} ago"
                else:
                    years = days_diff // 365
                    relative_time = f"in {years} year{'s' if years != 1 else ''}"
                
                formatted_time["relative"] = relative_time
                
                result = NodeResult(
                    output=formatted_time,
                    type="object",
                    execution_time=time.time() - start_time,
                    status="success",
                    node_id=node_id,
                    node_name=node_data.get("name", "Time")
                )
            except Exception as e:
                logger.error(f"Error processing time node: {str(e)}", exc_info=True)
                result = NodeResult(
                    output={
                        "error": f"Time node error: {str(e)}",
                        "timezone": timezone_str,
                        "operation": time_operation,
                        "current_time": datetime.datetime.now().isoformat()
                    },
                    type="object",
                    execution_time=time.time() - start_time,
                    status="error",
                    error=str(e),
                    node_id=node_id,
                    node_name=node_data.get("name", "Time")
                )
        
        # ... existing node handlers ...
        
        # GitHub Integration Node
        elif node_type == "github_node":
            # First check if user has GitHub credentials
            credentials = await request.app.mongodb["integration_credentials"].find_one({
                "user_id": user_id,
                "integration_type": IntegrationType.GITHUB
            })
            
            if not credentials:
                raise ValueError("You need to connect your GitHub account before using GitHub nodes. Go to /integrations to connect.")
                
            action = node_data.get("action", "list_repos")
            
            # Extract node parameters
            action_data = {}
            
            # Add parameters based on the selected action
            if action in ["create_issue", "create_pull_request", "get_repo_info", "list_issues", "get_issue", "list_branches", "create_comment"]:
                action_data["repo_owner"] = node_data.get("repo_owner", "")
                action_data["repo_name"] = node_data.get("repo_name", "")
                
            if action in ["get_issue", "create_comment"]:
                action_data["issue_number"] = int(node_data.get("issue_number", 0))
                
            if action in ["create_issue", "create_pull_request"]:
                action_data["title"] = node_data.get("title", "")
                action_data["body"] = node_data.get("body", "")
                
            if action == "create_pull_request":
                action_data["head"] = node_data.get("head", "")
                action_data["base"] = node_data.get("base", "main")
                
            if action == "list_issues":
                action_data["state"] = node_data.get("state", "open")
                
            if action == "create_comment":
                action_data["body"] = node_data.get("body", "")
            
            # Override with dynamic inputs if provided
            if isinstance(inputs.get("input"), dict):
                action_data.update(inputs.get("input", {}))
            
            # Call the GitHub API via our integrations router
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{request.url.scheme}://{request.url.netloc}/api/integrations/github/{action}",
                    headers={"Authorization": f"Bearer {request.headers.get('Authorization', '').split(' ')[1]}"},
                    json=action_data
                )
                
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"GitHub API error: {response.text}"
                    )
                    
                result = NodeResult(
                    output=response.json(),
                    type="object",
                    execution_time=time.time() - start_time,
                    status="success",
                    node_id=node_id,
                    node_name=node_data.get("name", f"GitHub - {action}")
                )
        
        # Airtable Integration Node
        elif node_type == "airtable_node":
            # First check if user has Airtable credentials
            credentials = await request.app.mongodb["integration_credentials"].find_one({
                "user_id": user_id,
                "integration_type": IntegrationType.AIRTABLE
            })
            
            if not credentials:
                raise ValueError("You need to connect your Airtable account before using Airtable nodes. Go to /integrations to connect.")
                
            action = node_data.get("action", "list_bases")
            
            # Extract node parameters
            action_data = {}
            
            # Add parameters based on the selected action
            if action in ["list_records", "get_record", "create_record", "update_record", "delete_record", "list_tables"]:
                action_data["base_id"] = node_data.get("base_id", "")
                
            if action in ["list_records", "get_record", "create_record", "update_record", "delete_record"]:
                action_data["table_id"] = node_data.get("table_id", "")
                
            if action in ["get_record", "update_record", "delete_record"]:
                action_data["record_id"] = node_data.get("record_id", "")
                
            if action == "list_records":
                if node_data.get("max_records"):
                    action_data["max_records"] = int(node_data.get("max_records", 100))
                if node_data.get("view"):
                    action_data["view"] = node_data.get("view", "")
                
            if action in ["create_record", "update_record"]:
                fields_str = node_data.get("fields", "{}")
                try:
                    action_data["fields"] = json.loads(fields_str) if isinstance(fields_str, str) else fields_str
                except Exception as e:
                    raise ValueError(f"Invalid JSON for fields: {e}")
            
            # Override with dynamic inputs if provided
            if isinstance(inputs.get("input"), dict):
                action_data.update(inputs.get("input", {}))
            
            # Call the Airtable API via our integrations router
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{request.url.scheme}://{request.url.netloc}/api/integrations/airtable/{action}",
                    headers={"Authorization": f"Bearer {request.headers.get('Authorization', '').split(' ')[1]}"},
                    json=action_data
                )
                
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Airtable API error: {response.text}"
                    )
                    
                result = NodeResult(
                    output=response.json(),
                    type="object",
                    execution_time=time.time() - start_time,
                    status="success",
                    node_id=node_id,
                    node_name=node_data.get("name", f"Airtable - {action}")
                )
        
        # Notion Integration Node
        elif node_type == "notion_node":
            # First check if user has Notion credentials
            credentials = await request.app.mongodb["integration_credentials"].find_one({
                "user_id": user_id,
                "integration_type": IntegrationType.NOTION
            })
            
            if not credentials:
                raise ValueError("You need to connect your Notion account before using Notion nodes. Go to /integrations to connect.")
                
            action = node_data.get("action", "list_databases")
            
            # Extract node parameters
            action_data = {}
            
            # Add parameters based on the selected action
            if action == "list_databases" and node_data.get("page_size"):
                action_data["page_size"] = int(node_data.get("page_size", 100))
                
            if action == "query_database":
                action_data["database_id"] = node_data.get("database_id", "")
                filter_str = node_data.get("filter", "null")
                sorts_str = node_data.get("sorts", "null")
                try:
                    if filter_str and filter_str.lower() != "null":
                        action_data["filter"] = json.loads(filter_str) if isinstance(filter_str, str) else filter_str
                    if sorts_str and sorts_str.lower() != "null":
                        action_data["sorts"] = json.loads(sorts_str) if isinstance(sorts_str, str) else sorts_str
                except Exception as e:
                    raise ValueError(f"Invalid JSON for filter or sorts: {e}")
                
            if action in ["get_page", "update_page"]:
                action_data["page_id"] = node_data.get("page_id", "")
                
            if action in ["create_page", "create_comment"]:
                action_data["parent_id"] = node_data.get("parent_id", "")
                action_data["parent_type"] = node_data.get("parent_type", "database_id")
                
            if action in ["create_page", "update_page"]:
                properties_str = node_data.get("properties", "{}")
                try:
                    action_data["properties"] = json.loads(properties_str) if isinstance(properties_str, str) else properties_str
                except Exception as e:
                    raise ValueError(f"Invalid JSON for properties: {e}")
                
            if action == "create_page" and node_data.get("content"):
                content_str = node_data.get("content", "null")
                try:
                    if content_str and content_str.lower() != "null":
                        action_data["content"] = json.loads(content_str) if isinstance(content_str, str) else content_str
                except Exception as e:
                    raise ValueError(f"Invalid JSON for content: {e}")
                
            if action == "create_comment":
                action_data["comment_text"] = node_data.get("comment_text", "")
            
            # Override with dynamic inputs if provided
            if isinstance(inputs.get("input"), dict):
                action_data.update(inputs.get("input", {}))
            
            # Call the Notion API via our integrations router
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{request.url.scheme}://{request.url.netloc}/api/integrations/notion/{action}",
                    headers={"Authorization": f"Bearer {request.headers.get('Authorization', '').split(' ')[1]}"},
                    json=action_data
                )
                
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Notion API error: {response.text}"
                    )
                    
                result = NodeResult(
                    output=response.json(),
                    type="object",
                    execution_time=time.time() - start_time,
                    status="success",
                    node_id=node_id,
                    node_name=node_data.get("name", f"Notion - {action}")
                )
                
        # Condition Node
        elif node_type == "condition":
            logger.info(f"Executing condition node {node_id}")
            
            # Get condition paths from node data
            paths = node_data.get("params", {}).get("paths", [])
            if not paths:
                # Always provide at least two default paths (true/false) if none defined
                paths = [
                    {"name": "True Path", "clauses": [], "logicalOperator": "AND"},
                    {"name": "False Path (Else)", "clauses": []}
                ]
                logger.warning(f"Condition node {node_id} had no paths, added default true/false paths")
            
            # Get input value to test against conditions
            input_value = inputs.get("input")
            logger.info(f"Condition input value: {input_value}")
            
            # Parse input value if it's a string that looks like JSON
            if isinstance(input_value, str):
                try:
                    if (input_value.startswith('{') and input_value.endswith('}')) or \
                       (input_value.startswith('[') and input_value.endswith(']')):
                        parsed_value = json.loads(input_value)
                        input_value = parsed_value
                        logger.info(f"Parsed JSON string input to object: {type(input_value)}")
                except json.JSONDecodeError:
                    # Keep as string if not valid JSON
                    pass
            
            # Determine which path to take
            selected_path_index = None
            evaluation_results = []
            
            # Check each path (except the last one, which is usually the ELSE path)
            for i, path in enumerate(paths[:-1] if len(paths) > 1 else paths):
                path_name = path.get("name", f"Path {i+1}")
                clauses = path.get("clauses", [])
                logical_operator = path.get("logicalOperator", "AND")
                
                # Skip empty path definitions
                if not clauses:
                    evaluation_results.append({"path": path_name, "result": False, "reason": "No clauses defined"})
                    continue
                
                # Evaluate all clauses with AND/OR logic
                clause_results = []
                clause_details = []
                
                for clause in clauses:
                    input_field = clause.get("inputField")
                    operator = clause.get("operator")
                    compare_value = clause.get("value")
                    
                    # Skip invalid clauses
                    if not input_field or not operator:
                        clause_details.append({
                            "field": input_field or "undefined",
                            "operator": operator or "undefined",
                            "value": compare_value,
                            "result": False,
                            "reason": "Invalid clause configuration"
                        })
                        clause_results.append(False)
                        continue
                    
                    # Extract field value from input (support for nested fields using dot notation)
                    field_value = input_value
                    field_exists = True
                    
                    if isinstance(input_value, dict):
                        for key in input_field.split('.'):
                            if key and isinstance(field_value, dict) and key in field_value:
                                field_value = field_value[key]
                            else:
                                field_value = None
                                field_exists = False
                                break
                    
                    # If field doesn't exist, handle based on operator
                    if not field_exists and operator not in ["is_empty", "is_not_empty"]:
                        clause_details.append({
                            "field": input_field,
                            "operator": operator,
                            "value": compare_value,
                            "field_value": None,
                            "result": False,
                            "reason": "Field not found in input"
                        })
                        clause_results.append(False)
                        continue
                    
                    # Convert values for comparison if needed
                    try:
                        # Try numeric conversion for both field value and compare value
                        if isinstance(compare_value, str):
                            # Try numeric conversion
                            if compare_value.lower() == "true":
                                compare_value = True
                            elif compare_value.lower() == "false":
                                compare_value = False
                            elif compare_value.replace('.', '', 1).isdigit():
                                if '.' in compare_value:
                                    compare_value = float(compare_value)
                                else:
                                    compare_value = int(compare_value)
                                
                        if isinstance(field_value, str):
                            # Try boolean conversion
                            if field_value.lower() == "true":
                                field_value = True
                            elif field_value.lower() == "false":
                                field_value = False
                            # Try numeric conversion
                            elif field_value.replace('.', '', 1).isdigit():
                                if '.' in field_value:
                                    field_value = float(field_value)
                                else:
                                    field_value = int(field_value)
                    except (ValueError, TypeError, AttributeError):
                        # If conversion fails, use as is
                        pass
                    
                    # Evaluate the clause based on the operator
                    clause_result = False
                    reason = "Comparison failed"
                    date_range = None  # Define date_range outside the try block
                    
                    try:
                        if operator == "==":
                            clause_result = field_value == compare_value
                            reason = f"{field_value} == {compare_value}"
                        elif operator == "!=":
                            clause_result = field_value != compare_value
                            reason = f"{field_value} != {compare_value}"
                        elif operator == ">":
                            clause_result = field_value > compare_value
                            reason = f"{field_value} > {compare_value}"
                        elif operator == ">=":
                            clause_result = field_value >= compare_value
                            reason = f"{field_value} >= {compare_value}"
                        elif operator == "<":
                            clause_result = field_value < compare_value
                            reason = f"{field_value} < {compare_value}"
                        elif operator == "<=":
                            clause_result = field_value <= compare_value
                            reason = f"{field_value} <= {compare_value}"
                        elif operator == "contains":
                            if isinstance(field_value, str) and isinstance(compare_value, str):
                                clause_result = compare_value in field_value
                                reason = f"'{compare_value}' in '{field_value}'"
                            elif isinstance(field_value, (list, tuple, set)):
                                clause_result = compare_value in field_value
                                reason = f"{compare_value} in {field_value}"
                            elif isinstance(field_value, dict):
                                clause_result = compare_value in field_value.keys() or compare_value in field_value.values()
                                reason = f"{compare_value} in dict keys/values"
                        elif operator == "not_contains":
                            if isinstance(field_value, str) and isinstance(compare_value, str):
                                clause_result = compare_value not in field_value
                                reason = f"'{compare_value}' not in '{field_value}'"
                            elif isinstance(field_value, (list, tuple, set)):
                                clause_result = compare_value not in field_value
                                reason = f"{compare_value} not in {field_value}"
                            elif isinstance(field_value, dict):
                                clause_result = compare_value not in field_value.keys() and compare_value not in field_value.values()
                                reason = f"{compare_value} not in dict keys/values"
                        elif operator == "startswith":
                            if isinstance(field_value, str) and isinstance(compare_value, str):
                                clause_result = field_value.startswith(compare_value)
                                reason = f"'{field_value}' startswith '{compare_value}'"
                        elif operator == "endswith":
                            if isinstance(field_value, str) and isinstance(compare_value, str):
                                clause_result = field_value.endswith(compare_value)
                                reason = f"'{field_value}' endswith '{compare_value}'"
                        elif operator == "is_empty":
                            clause_result = field_value is None or field_value == "" or field_value == [] or field_value == {} or not field_exists
                            reason = "Field is empty or doesn't exist"
                        elif operator == "is_not_empty":
                            clause_result = field_value is not None and field_value != "" and field_value != [] and field_value != {} and field_exists
                            reason = "Field is not empty"
                        elif operator == "matches_regex":
                            # Add regex pattern matching
                            if isinstance(field_value, str) and isinstance(compare_value, str):
                                try:
                                    import re
                                    clause_result = bool(re.search(compare_value, field_value))
                                    reason = f"'{field_value}' matches regex '{compare_value}'"
                                except re.error as e:
                                    logger.error(f"Invalid regex pattern: {compare_value}. Error: {str(e)}")
                                    reason = f"Invalid regex: {str(e)}"
                                    clause_result = False
                        elif operator == "in_list":
                            # Check if field value is in a list
                            if isinstance(compare_value, str):
                                try:
                                    items = [item.strip() for item in compare_value.split(',')]
                                    clause_result = str(field_value) in items
                                    reason = f"'{field_value}' in list {items}"
                                except Exception as e:
                                    reason = f"Invalid list format: {str(e)}"
                                    clause_result = False
                            elif isinstance(compare_value, (list, tuple)):
                                clause_result = field_value in compare_value
                                reason = f"{field_value} in {compare_value}"
                        elif operator == "not_in_list":
                            # Check if field value is not in a list
                            if isinstance(compare_value, str):
                                try:
                                    items = [item.strip() for item in compare_value.split(',')]
                                    clause_result = str(field_value) not in items
                                    reason = f"'{field_value}' not in list {items}"
                                except Exception as e:
                                    reason = f"Invalid list format: {str(e)}"
                                    clause_result = False
                            elif isinstance(compare_value, (list, tuple)):
                                clause_result = field_value not in compare_value
                                reason = f"{field_value} not in {compare_value}"
                        elif operator == "length_equals":
                            # Check if length of field value equals compare value
                            try:
                                length = len(field_value)
                                if isinstance(compare_value, (int, float)):
                                    clause_result = length == compare_value
                                else:
                                    clause_result = length == int(compare_value)
                                reason = f"len({field_value}) == {compare_value}"
                            except (TypeError, ValueError):
                                reason = "Cannot determine length"
                                clause_result = False
                        elif operator == "length_greater_than":
                            # Check if length of field value is greater than compare value
                            try:
                                length = len(field_value)
                                if isinstance(compare_value, (int, float)):
                                    clause_result = length > compare_value
                                else:
                                    clause_result = length > int(compare_value)
                                reason = f"len({field_value}) > {compare_value}"
                            except (TypeError, ValueError):
                                reason = "Cannot determine length"
                                clause_result = False
                        elif operator == "length_less_than":
                            # Check if length of field value is less than compare value
                            try:
                                length = len(field_value)
                                if isinstance(compare_value, (int, float)):
                                    clause_result = length < compare_value
                                else:
                                    clause_result = length < int(compare_value)
                                reason = f"len({field_value}) < {compare_value}"
                            except (TypeError, ValueError):
                                reason = "Cannot determine length"
                                clause_result = False
                        elif operator in ["date_before", "date_after", "date_equals", "date_between"]:
                            # Enhanced date comparison
                            try:
                                # Parse field_value as date with improved handling
                                field_date = None
                                if isinstance(field_value, datetime.datetime):
                                    field_date = field_value
                                elif isinstance(field_value, str):
                                    # Try common date formats
                                    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y/%m/%d", 
                                               "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y", 
                                               "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", 
                                               "%d/%m/%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                                               "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
                                        try:
                                            field_date = datetime.datetime.strptime(field_value, fmt)
                                            break
                                        except ValueError:
                                            continue
                                    # If still not parsed, try timestamp
                                    if not field_date and field_value.isdigit():
                                        field_date = datetime.datetime.fromtimestamp(int(field_value))
                                elif isinstance(field_value, (int, float)):
                                    # Assume timestamp
                                    field_date = datetime.datetime.fromtimestamp(field_value)
                                
                                if not field_date:
                                    reason = f"Could not parse date from '{field_value}'"
                                    clause_result = False
                                    logger.warning(reason)
                                else:
                                    # Handle different date comparison operators
                                    if operator == "date_between":
                                        # For date_between, parse two dates from compare_value
                                        date_range = None
                                        if isinstance(compare_value, str):
                                            # Expecting format like "2023-01-01,2023-12-31"
                                            date_parts = compare_value.split(',')
                                            if len(date_parts) == 2:
                                                start_date = None
                                                end_date = None
                                                # Try to parse both dates
                                                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
                                                    try:
                                                        if not start_date:
                                                            start_date = datetime.datetime.strptime(date_parts[0].strip(), fmt)
                                                        if not end_date:
                                                            end_date = datetime.datetime.strptime(date_parts[1].strip(), fmt)
                                                        if start_date and end_date:
                                                            break
                                                    except ValueError:
                                                        continue
                                                
                                                if start_date and end_date:
                                                    date_range = (start_date, end_date)
                                
                                if date_range:
                                    clause_result = date_range[0] <= field_date <= date_range[1]
                                    reason = f"{date_range[0]} <= {field_date} <= {date_range[1]}"
                                else:
                                    reason = f"Invalid date range format: {compare_value}"
                                    clause_result = False
                            else:
                                # Parse single comparison date
                                compare_date = None
                                if isinstance(compare_value, datetime.datetime):
                                    compare_date = compare_value
                                elif isinstance(compare_value, str):
                                    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y/%m/%d", 
                                                       "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y",
                                                       "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", 
                                                       "%d/%m/%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                                                       "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
                                                try:
                                                    compare_date = datetime.datetime.strptime(compare_value, fmt)
                                                    break
                                                except ValueError:
                                                    continue
                                            # If still not parsed, try timestamp
                                            if not compare_date and compare_value.isdigit():
                                                compare_date = datetime.datetime.fromtimestamp(int(compare_value))
                                        elif isinstance(compare_value, (int, float)):
                                            compare_date = datetime.datetime.fromtimestamp(compare_value)
                                        
                                        if compare_date:
                                            if operator == "date_before":
                                                clause_result = field_date < compare_date
                                                reason = f"{field_date} < {compare_date}"
                                            elif operator == "date_after":
                                                clause_result = field_date > compare_date
                                                reason = f"{field_date} > {compare_date}"
                                            elif operator == "date_equals":
                                                # Compare only the date part, not time
                                                clause_result = field_date.date() == compare_date.date()
                                                reason = f"{field_date.date()} == {compare_date.date()}"
                                            else:
                                                reason = f"Unknown date operator: {operator}"
                                                clause_result = False
                                        else:
                                            reason = f"Could not parse comparison date: {compare_value}"
                                            clause_result = False
                            except Exception as e:
                                logger.error(f"Error comparing dates: {str(e)}", exc_info=True)
                                reason = f"Date comparison error: {str(e)}"
                                clause_result = False
                    except Exception as e:
                        logger.error(f"Error comparing dates: {str(e)}", exc_info=True)
                        reason = f"Date comparison error: {str(e)}"
                        clause_result = False
                
                # Add clause result
                clause_details.append({
                    "field": input_field,
                    "operator": operator,
                    "value": compare_value,
                    "field_value": field_value,
                    "result": clause_result,
                    "reason": reason
                })
                clause_results.append(clause_result)
            
            # Combine clause results based on logical operator
            path_result = False
            
            if logical_operator == "AND":
                path_result = all(clause_results) if clause_results else False
                reason = "All conditions met" if path_result else "Not all conditions met"
            else:  # OR
                path_result = any(clause_results) if clause_results else False
                reason = "At least one condition met" if path_result else "No conditions met"
            
            evaluation_results.append({
                "path": path_name,
                "result": path_result,
                "reason": reason,
                "clauses": clause_details
            })
            
            if path_result:
                selected_path_index = i
                break
        
        # If no path matches, use the last path (ELSE) if available
        if selected_path_index is None and len(paths) > 1:
            selected_path_index = len(paths) - 1
            evaluation_results.append({
                "path": paths[-1].get("name", f"Path {len(paths)}") or "Else Path",
                "result": True,
                "reason": "Default else path selected"
            })
        
        # Construct the output with the path index
        logger.info(f"Condition node selected path: {selected_path_index}")
        
        result = NodeResult(
            output={
                "selected_path": selected_path_index,
                "value": input_value,
                "evaluation": evaluation_results
            },
            type="object",
            execution_time=time.time() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("name", "Condition")
        )
        
        return result
        
    except Exception as e:
        # Log the error
        execution_time = time.time() - start_time
        logger.error(f"Error executing node {node_id} ({node_type}): {str(e)}", exc_info=True)
        
        # Return error result
        return NodeResult(
            output=None,
            type="null",
            execution_time=execution_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("name", node_type.capitalize() if node_type else "Unknown")
        )

# Helper function to find nodes that depend on the output of a given node
def get_dependent_nodes(node_id, edges, remaining_nodes):
    """Find nodes that directly or indirectly depend on the output of a given node"""
    # Get direct dependent nodes
    direct_dependents = [edge["target"] for edge in edges if edge["source"] == node_id]
    
    # Filter only nodes that are in the remaining execution order
    dependent_nodes = [
        node for node in remaining_nodes 
        if node["id"] in direct_dependents
    ]
    
    return dependent_nodes

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

# Text to SQL Node
elif node_type == "ttsql":
    logger.info(f"Executing text to SQL node {node_id}")
    
    # Get query and schema from node data
    query = node_data.get("params", {}).get("query", "")
    schema = node_data.get("params", {}).get("schema", "")
    database_type = node_data.get("params", {}).get("database", "MySQL")
    parameters = node_data.get("params", {}).get("parameters", {})
    validate_only = node_data.get("params", {}).get("validateOnly", True)
    execute_query = node_data.get("params", {}).get("executeQuery", False)
    connection_string = node_data.get("params", {}).get("connectionString", "")
    model = node_data.get("params", {}).get("model", "gpt-3.5-turbo")
    explain_query = node_data.get("params", {}).get("explainQuery", False)
    save_query = node_data.get("params", {}).get("saveQuery", False)
    query_history = node_data.get("params", {}).get("queryHistory", [])
    max_tokens = node_data.get("params", {}).get("maxTokens", 600)
    
    # Validate required inputs
    input_errors = []
    if not query:
        input_errors.append("Missing natural language query")
    if not schema:
        input_errors.append("Missing database schema")
    
    # Override with input if available
    input_value = inputs.get("input")
    if isinstance(input_value, dict):
        if "query" in input_value:
            query = input_value["query"]
        if "schema" in input_value:
            schema = input_value["schema"]
        if "parameters" in input_value and isinstance(input_value["parameters"], dict):
            parameters = input_value["parameters"]
        if "database_type" in input_value:
            database_type = input_value["database_type"]
        if "execute_query" in input_value:
            execute_query = bool(input_value["execute_query"])
        if "connection_string" in input_value:
            connection_string = input_value["connection_string"]
    elif isinstance(input_value, str) and input_value:
        # If input is a string, use it as the query
        query = input_value
    
    # Resolve any parameter placeholders in the query
    if parameters and isinstance(parameters, dict):
        try:
            for key, value in parameters.items():
                placeholder = f"{{{key}}}"
                if placeholder in query:
                    query = query.replace(placeholder, str(value))
        except Exception as e:
            logger.warning(f"Error replacing parameters in query: {str(e)}")
    
    # Set normalized database type for consistent handling
    db_type_map = {
        "mysql": "MySQL",
        "mariadb": "MySQL",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "sqlite": "SQLite",
        "mssql": "SQL Server",
        "sqlserver": "SQL Server",
        "oracle": "Oracle",
    }
    normalized_db_type = db_type_map.get(database_type.lower(), database_type)
    
    # Check if any input errors occurred
    if input_errors:
        error_message = "; ".join(input_errors)
        logger.error(f"Text to SQL input errors: {error_message}")
        result = NodeResult(
            output={
                "error": error_message,
                "sql": "",
                "original_query": query,
                "database_type": normalized_db_type
            },
            type="object",
            execution_time=time.time() - start_time,
            status="error",
            error=error_message,
            node_id=node_id,
            node_name=node_data.get("name", "Text to SQL")
        )
    else:
        try:
            # Use OpenAI to convert natural language to SQL
            import openai
            
            # Check if API key is available
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not configured for Text to SQL conversion")
            
            # Create OpenAI client
            client = openai.OpenAI(api_key=api_key)
            
            # Format parameters for the prompt
            parameters_str = ""
            if parameters:
                parameters_str = "With the following parameters:\n\n"
                for param_name, param_value in parameters.items():
                    parameters_str += f"- {param_name}: {param_value}\n"
            
            # Add examples to the prompt if available
            examples_str = ""
            if query_history and len(query_history) > 0:
                examples_str = "Here are some examples of previous queries and their SQL translations:\n\n"
                for i, example in enumerate(query_history[:3]):  # Limit to 3 examples
                    if isinstance(example, dict) and "query" in example and "sql" in example:
                        examples_str += f"Example {i+1}:\nQuery: {example['query']}\nSQL: {example['sql']}\n\n"
            
            # Add database-specific guidelines
            db_guidelines = ""
            if normalized_db_type == "MySQL":
                db_guidelines = "- Use backticks (`) for table and column names\n- Use LIMIT for pagination\n- For string comparisons, use LIKE with % wildcards\n"
            elif normalized_db_type == "PostgreSQL":
                db_guidelines = "- Use double quotes (\") for table and column names\n- Use LIMIT for pagination\n- For string comparisons, use ILIKE for case-insensitive matches\n- Use :: for type casting\n"
            elif normalized_db_type == "SQLite":
                db_guidelines = "- No need for quotes around table and column names\n- Use LIMIT for pagination\n- For date operations, use the built-in date functions\n"
            elif normalized_db_type == "SQL Server":
                db_guidelines = "- Use square brackets ([]) for table and column names\n- Use TOP instead of LIMIT for pagination\n- For string comparisons, use LIKE with % wildcards\n"
            elif normalized_db_type == "Oracle":
                db_guidelines = "- Use double quotes (\") for table and column names\n- Use ROWNUM for pagination\n- For date operations, use TO_DATE and TO_CHAR functions\n"
            
            # Create a prompt for the SQL conversion
            prompt = f"""
            Based on the following database schema:
            
            {schema}
            
            {parameters_str}
            
            {examples_str if examples_str else ""}
            
            Guidelines for {normalized_db_type} SQL:
            {db_guidelines}
            
            Convert this natural language query to SQL ({normalized_db_type}):
            
            {query}
            
            Return ONLY the SQL query with no explanation or other text.
            """
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a SQL expert. Convert natural language to SQL queries accurately."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=max_tokens
            )
            
            # Extract SQL from the response
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the SQL (remove markdown code blocks if present)
            if sql_query.startswith("```") and sql_query.endswith("```"):
                sql_query = sql_query.strip("```")
                # Remove language identifier if present
                if sql_query.startswith("sql"):
                    sql_query = sql_query[3:].strip()
                else:
                    # Remove any other language identifier
                    lines = sql_query.split("\n")
                    if len(lines) > 1 and not lines[0].strip().upper().startswith("SELECT"):
                        sql_query = "\n".join(lines[1:])
            
            # Generate explanation if requested
            sql_explanation = ""
            if explain_query:
                try:
                    explanation_prompt = f"""
                    Explain the following SQL query in simple terms:
                    
                    ```sql
                    {sql_query}
                    ```
                    
                    Explain what the query does, any joins, conditions, and the expected results.
                    """
                    
                    explanation_response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are a SQL expert explaining queries to non-technical users."},
                            {"role": "user", "content": explanation_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=300
                    )
                    
                    sql_explanation = explanation_response.choices[0].message.content.strip()
                except Exception as e:
                    logger.warning(f"Failed to generate SQL explanation: {str(e)}")
                    sql_explanation = "Explanation not available due to an error."
            
            # Validate the SQL syntax
            validation_result = {"valid": True, "errors": []}
            
            try:
                # Use appropriate validator based on database type
                if normalized_db_type == "MySQL":
                    try:
                        import sqlparse
                        parsed = sqlparse.parse(sql_query)
                        if not parsed:
                            validation_result = {"valid": False, "errors": ["Failed to parse SQL query"]}
                        elif sql_query.count(';') > 1:
                            validation_result = {"valid": False, "errors": ["Multiple statements detected"]}
                    except ImportError:
                        logger.warning("sqlparse not installed, skipping validation")
                elif normalized_db_type == "PostgreSQL":
                    # Light validation using regex patterns
                    import re
                    # Check for common SQL injection patterns
                    if re.search(r';\s*DROP\s+TABLE', sql_query, re.IGNORECASE):
                        validation_result = {"valid": False, "errors": ["Possible SQL injection detected: DROP TABLE"]}
                    elif re.search(r';\s*DELETE\s+FROM', sql_query, re.IGNORECASE):
                        validation_result = {"valid": False, "errors": ["Possible SQL injection detected: DELETE FROM"]}
                    elif sql_query.count(';') > 1:
                        validation_result = {"valid": False, "errors": ["Multiple statements detected"]}
                    
                    # For more thorough validation of PostgreSQL, psycopg2 would be needed
                elif normalized_db_type == "SQLite":
                    try:
                        import sqlite3
                        # Create an in-memory database and try parsing the query
                        conn = sqlite3.connect(":memory:")
                        try:
                            conn.execute("EXPLAIN " + sql_query)
                        except sqlite3.Error as e:
                            validation_result = {"valid": False, "errors": [str(e)]}
                            conn.execute(f"EXPLAIN {sql_query}")
                        except sqlite3.Error as e:
                            validation_result = {"valid": False, "errors": [str(e)]}
                        conn.close()
                    except (ImportError, sqlite3.Error) as e:
                        logger.warning(f"SQLite validation error: {str(e)}")
            except ImportError:
                validation_result = {"valid": True, "errors": ["Validation libraries not available"]}
            except Exception as e:
                validation_result = {"valid": False, "errors": [f"Validation error: {str(e)}"]}
            
            # Execute the SQL query if requested and validation passed
            execution_result = None
            if execute_query and validation_result["valid"] and connection_string:
                try:
                    # Determine which database driver to use
                    if normalized_db_type == "MySQL":
                        try:
                            import mysql.connector
                            
                            # Parse connection string
                            # Expected format: mysql://user:pass@host:port/dbname
                            conn_parts = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', connection_string)
                            if conn_parts:
                                user, password, host, port, db = conn_parts.groups()
                                conn = mysql.connector.connect(
                                    user=user,
                                    password=password,
                                    host=host,
                                    port=int(port),
                                    database=db
                                )
                                cursor = conn.cursor(dictionary=True)
                                cursor.execute(sql_query)
                                
                                # Check if it's a SELECT query
                                is_select = sql_query.strip().upper().startswith("SELECT")
                                
                                if is_select:
                                    rows = cursor.fetchall()
                                    # Convert decimal.Decimal to float for JSON serialization
                                    for row in rows:
                                        for key, value in row.items():
                                            if isinstance(value, decimal.Decimal):
                                                row[key] = float(value)
                                    
                                    execution_result = {
                                        "rows": rows,
                                        "rowCount": len(rows),
                                        "columnCount": len(rows[0]) if rows else 0,
                                        "columns": list(rows[0].keys()) if rows else []
                                    }
                                else:
                                    execution_result = {
                                        "rowCount": cursor.rowcount,
                                        "affectedRows": cursor.rowcount,
                                        "lastInsertId": cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
                                    }
                                
                                cursor.close()
                                conn.close()
                            else:
                                raise ValueError("Invalid MySQL connection string format. Expected: mysql://user:pass@host:port/dbname")
                        except ImportError:
                            raise ValueError("MySQL driver not installed. Install with: pip install mysql-connector-python")
                    
                    elif normalized_db_type == "PostgreSQL":
                        try:
                            import psycopg2
                            import psycopg2.extras
                            
                            conn = psycopg2.connect(connection_string)
                            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                            cursor.execute(sql_query)
                            
                            # Check if it's a SELECT query
                            is_select = sql_query.strip().upper().startswith("SELECT")
                            
                            if is_select:
                                rows = cursor.fetchall()
                                execution_result = {
                                    "rows": [dict(row) for row in rows],  # Convert to regular dict
                                    "rowCount": len(rows),
                                    "columnCount": len(rows[0]) if rows else 0,
                                    "columns": list(rows[0].keys()) if rows else []
                                }
                            else:
                                execution_result = {
                                    "rowCount": cursor.rowcount,
                                    "affectedRows": cursor.rowcount
                                }
                            
                            cursor.close()
                            conn.close()
                        except ImportError:
                            raise ValueError("PostgreSQL driver not installed. Install with: pip install psycopg2-binary")
                    
                    elif normalized_db_type == "SQLite":
                        try:
                            import sqlite3
                            
                            # SQLite connection string is the path to the database file
                            conn = sqlite3.connect(connection_string)
                            conn.row_factory = sqlite3.Row
                            cursor = conn.cursor()
                            cursor.execute(sql_query)
                            
                            # Check if it's a SELECT query
                            is_select = sql_query.strip().upper().startswith("SELECT")
                            
                            if is_select:
                                rows = cursor.fetchall()
                                execution_result = {
                                    "rows": [dict(row) for row in rows],  # Convert to regular dict
                                    "rowCount": len(rows),
                                    "columnCount": len(rows[0]) if rows else 0,
                                    "columns": list(rows[0].keys()) if rows else []
                                }
                            else:
                                execution_result = {
                                    "rowCount": cursor.rowcount,
                                    "affectedRows": cursor.rowcount,
                                    "lastInsertId": cursor.lastrowid if cursor.lastrowid > 0 else None
                                }
                            
                            cursor.close()
                            conn.close()
                        except ImportError:
                            raise ValueError("SQLite is not available")
                    
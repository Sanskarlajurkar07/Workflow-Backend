import logging
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_api_loader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for api_loader node type to make HTTP requests"""
    logger.info(f"Executing API Loader node {node_id}")
    
    # Extract parameters
    method = node_data.get("params", {}).get("method", "GET")
    url = node_data.get("params", {}).get("url", "")
    headers = node_data.get("params", {}).get("headers", [])
    query_params = node_data.get("params", {}).get("queryParams", [])
    body = node_data.get("params", {}).get("body", "")
    body_type = node_data.get("params", {}).get("bodyType", "raw")
    node_name = node_data.get("params", {}).get("nodeName", f"api_{node_id[:4]}")
    
    # Process variable replacements in URL
    for key, value in inputs.items():
        url = url.replace(f"{{{{{key}}}}}", str(value))
    
    # Convert headers from array of objects to dictionary
    headers_dict = {}
    for header in headers:
        if header.get("key") and header.get("value"):
            # Also replace variables in header values
            header_value = header.get("value", "")
            for key, value in inputs.items():
                header_value = header_value.replace(f"{{{{{key}}}}}", str(value))
            headers_dict[header.get("key")] = header_value
    
    # Convert query params from array of objects to dictionary
    params_dict = {}
    for param in query_params:
        if param.get("key") and param.get("value"):
            # Also replace variables in query parameter values
            param_value = param.get("value", "")
            for key, value in inputs.items():
                param_value = param_value.replace(f"{{{{{key}}}}}", str(value))
            params_dict[param.get("key")] = param_value
    
    # Process body if needed
    request_body = None
    if method in ["POST", "PUT", "PATCH"] and body:
        # Replace variables in body
        processed_body = body
        for key, value in inputs.items():
            processed_body = processed_body.replace(f"{{{{{key}}}}}", str(value))
        
        if body_type == "json":
            try:
                request_body = json.loads(processed_body)
                headers_dict["Content-Type"] = "application/json"
            except json.JSONDecodeError:
                return NodeResult(
                    output={"error": "Invalid JSON body"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="Invalid JSON body",
                    node_id=node_id,
                    node_name=node_name
                )
        else:
            request_body = processed_body
            headers_dict["Content-Type"] = "text/plain"
    
    try:
        # Make the API request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers_dict,
                params=params_dict,
                json=request_body if body_type == "json" and request_body else None,
                content=request_body if body_type == "raw" and request_body else None,
            )
            
            # Try to parse the response as JSON
            try:
                response_data = response.json()
                content_type = "application/json"
            except json.JSONDecodeError:
                response_data = response.text
                content_type = response.headers.get("Content-Type", "text/plain")
            
            # Create the result object
            result = {
                "status": response.status_code,
                "content": response_data,
                "headers": dict(response.headers),
                "content_type": content_type,
                "url": str(response.url),
                "success": 200 <= response.status_code < 300,
                "execution_time_ms": round((datetime.now().timestamp() - start_time) * 1000, 2)
            }
            
            # Store response in workflow data for variable access
            workflow_data[node_name] = result
            
            return NodeResult(
                output=result,
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="success" if 200 <= response.status_code < 300 else "error",
                error=f"HTTP {response.status_code}" if response.status_code >= 400 else None,
                node_id=node_id,
                node_name=node_name
            )
    except Exception as e:
        logger.error(f"Error in API Loader node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 
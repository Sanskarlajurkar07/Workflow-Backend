import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_json_handler_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any], 
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for json_handler node type
    
    This node processes and manipulates JSON data with various operations.
    """
    logger.info(f"Executing JSON Handler node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "parse")
    path = node_data.get("params", {}).get("path", "")
    format_output = node_data.get("params", {}).get("formatOutput", False)
    default_value = node_data.get("params", {}).get("defaultValue", None)
    transform_keys = node_data.get("params", {}).get("transformKeys", [])
    variable_name = node_data.get("params", {}).get("variableName", f"json_{node_id[:4]}")
    
    # Process variables in parameters
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if path and var_placeholder in path:
                path = path.replace(var_placeholder, str(value))
    
    # Get input data
    input_data = inputs.get("input", "")
    
    try:
        result = {}
        
        if operation == "parse":
            # Parse string to JSON
            if isinstance(input_data, str):
                try:
                    parsed_json = json.loads(input_data)
                    result = {
                        "data": parsed_json,
                        "operation": "parse",
                        "type": type(parsed_json).__name__
                    }
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON: {str(e)}")
            else:
                # Input is already parsed
                result = {
                    "data": input_data,
                    "operation": "parse",
                    "type": type(input_data).__name__,
                    "note": "Input was already a parsed object"
                }
        
        elif operation == "stringify":
            # Convert object to JSON string
            if format_output:
                json_string = json.dumps(input_data, indent=2)
            else:
                json_string = json.dumps(input_data)
                
            result = {
                "string": json_string,
                "operation": "stringify",
                "length": len(json_string),
                "formatted": format_output
            }
        
        elif operation == "extract":
            # Extract value from JSON path
            json_data = input_data
            if isinstance(input_data, str):
                try:
                    json_data = json.loads(input_data)
                except json.JSONDecodeError:
                    json_data = {"text": input_data}
            
            # Simple path navigation using dots (a.b.c)
            if path:
                parts = path.split('.')
                current = json_data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                        current = current[int(part)]
                    else:
                        current = default_value
                        break
                
                result = {
                    "value": current,
                    "operation": "extract",
                    "path": path,
                    "found": current != default_value
                }
            else:
                result = {
                    "value": json_data,
                    "operation": "extract",
                    "path": "",
                    "note": "No path specified, returning entire object"
                }
        
        elif operation == "transform":
            # Transform JSON structure
            json_data = input_data
            if isinstance(input_data, str):
                try:
                    json_data = json.loads(input_data)
                except json.JSONDecodeError:
                    json_data = {"text": input_data}
            
            transformed = {}
            # Apply transformations based on key mappings
            if isinstance(json_data, dict):
                for old_key, new_key in transform_keys:
                    if old_key in json_data:
                        transformed[new_key] = json_data[old_key]
            
            result = {
                "data": transformed,
                "operation": "transform",
                "original_keys": list(json_data.keys()) if isinstance(json_data, dict) else [],
                "new_keys": list(transformed.keys())
            }
        
        # Store result in workflow data for variable access
        result_value = result.get("data", result.get("value", result.get("string", result)))
        workflow_data[variable_name] = result_value
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "JSON Handler")
        )
    
    except Exception as e:
        logger.error(f"Error in JSON Handler node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "JSON Handler")
        ) 
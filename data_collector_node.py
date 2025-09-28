import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_data_collector_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for data_collector node type
    
    This node collects structured data from user inputs based on defined fields.
    """
    logger.info(f"Executing Data Collector node {node_id}")
    
    # Extract parameters
    query = node_data.get("params", {}).get("query", "Please provide the following information:")
    prompt = node_data.get("params", {}).get("prompt", "")
    fields = node_data.get("params", {}).get("fields", [])
    variable_name = node_data.get("params", {}).get("variableName", f"collected_data_{node_id[:4]}")
    
    # Process variables in query and prompt
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if var_placeholder in query:
                query = query.replace(var_placeholder, str(value))
            if prompt and var_placeholder in prompt:
                prompt = prompt.replace(var_placeholder, str(value))
    
    # In a real implementation, this would wait for user input through a UI
    # For this simulation, we'll generate mock data based on the fields
    
    # Create mock collected data
    collected_data = {}
    raw_inputs = []
    
    # Process each field
    for field in fields:
        field_name = field.get("name", "")
        field_type = field.get("type", "text")
        field_description = field.get("description", "")
        field_example = field.get("example", "")
        
        # Skip fields without a name
        if not field_name:
            continue
        
        # Generate mock value based on field type
        if field_type == "text":
            value = f"Sample {field_name} text"
        elif field_type == "number":
            value = 42
        elif field_type == "email":
            value = f"{field_name.lower()}@example.com"
        elif field_type == "date":
            value = datetime.now().strftime("%Y-%m-%d")
        elif field_type == "select" and "options" in field:
            options = field.get("options", [])
            value = options[0] if options else ""
        else:
            value = f"Sample value for {field_name}"
            
        # Store the value and record the raw input event
        collected_data[field_name] = value
        raw_inputs.append({
            "field": field_name,
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
    
    # Store result in workflow data for variable access
    workflow_data[variable_name] = collected_data
    
    # Prepare output
    output = {
        "collected_data": collected_data,
        "raw_inputs": raw_inputs,
        "query": query,
        "prompt": prompt,
        "fields": [f.get("name", "") for f in fields]
    }
    
    return NodeResult(
        output=output,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Data Collector")
    ) 
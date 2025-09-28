import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_chat_file_reader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for chat_file_reader node type
    
    This node processes files uploaded in chat or from predefined locations.
    """
    logger.info(f"Executing Chat File Reader node {node_id}")
    
    # Extract parameters
    file_type = node_data.get("params", {}).get("fileType", "all")
    max_file_size = node_data.get("params", {}).get("maxFileSize", 10)  # in MB
    selected_file = node_data.get("params", {}).get("selectedFile", "")
    variable_name = node_data.get("params", {}).get("variableName", f"file_data_{node_id[:4]}")
    
    # Process variables in selected file path
    if selected_file:
        for key, value in workflow_data.items():
            if isinstance(value, (str, int, float, bool)):
                var_placeholder = f"{{{{workflow.variables.{key}}}}}"
                if var_placeholder in selected_file:
                    selected_file = selected_file.replace(var_placeholder, str(value))
    
    # If input contains file data, use that instead of configured file
    input_data = inputs.get("input", None)
    if input_data and isinstance(input_data, dict) and "filename" in input_data:
        selected_file = input_data.get("filename", "")
        file_content = input_data.get("content", "")
        file_metadata = {
            "filename": selected_file,
            "size": len(file_content),
            "type": input_data.get("type", "application/octet-stream"),
            "uploaded_at": datetime.now().isoformat()
        }
    else:
        # In a real implementation, this would read from the file system
        # Here we provide simulated content
        if selected_file:
            file_content = f"This is the content of file: {selected_file}\n\nLine 1: Sample content\nLine 2: More sample content\n..."
            
            # Generate more realistic content based on file type
            if selected_file.endswith(".csv"):
                file_content = "id,name,email,department\n1,John Doe,john@example.com,Engineering\n2,Jane Smith,jane@example.com,Marketing\n3,Bob Johnson,bob@example.com,Finance"
            elif selected_file.endswith(".json"):
                file_content = '{\n  "users": [\n    {"id": 1, "name": "John", "role": "admin"},\n    {"id": 2, "name": "Jane", "role": "user"},\n    {"id": 3, "name": "Bob", "role": "user"}\n  ],\n  "settings": {\n    "theme": "dark",\n    "notifications": true\n  }\n}'
            elif selected_file.endswith(".md") or selected_file.endswith(".txt"):
                file_content = f"# {selected_file}\n\n## Overview\nThis is a sample document for demonstration purposes.\n\n## Details\n- Point 1\n- Point 2\n- Point 3\n\n## Conclusion\nThank you for reviewing this document."
            
            file_metadata = {
                "filename": selected_file,
                "size": len(file_content),
                "type": "text/plain",  # Simplified MIME type
                "uploaded_at": datetime.now().isoformat()
            }
        else:
            file_content = "No file has been selected. Please upload or select a file to process."
            file_metadata = {
                "filename": None,
                "size": 0,
                "type": None,
                "uploaded_at": None
            }
    
    # Store in workflow data for variable access
    result = {
        "content": file_content,
        "metadata": file_metadata,
        "filename": file_metadata.get("filename", None)
    }
    workflow_data[variable_name] = result
    
    return NodeResult(
        output=result,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Chat File Reader")
    ) 
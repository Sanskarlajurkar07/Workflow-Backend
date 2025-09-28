import logging
import base64
import json
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_file_transformer_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for file_transformer node type
    
    This node transforms file content between different formats.
    """
    logger.info(f"Executing File Transformer node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "convert")
    output_format = node_data.get("params", {}).get("outputFormat", "text")
    encoding = node_data.get("params", {}).get("encoding", "utf-8")
    variable_name = node_data.get("params", {}).get("variableName", f"transformed_file_{node_id[:4]}")
    
    # Get input file data
    input_data = inputs.get("input", {})
    
    try:
        result = {}
        
        # Check if input has file metadata
        file_content = None
        file_metadata = {}
        
        if isinstance(input_data, dict) and "content" in input_data:
            # Input is likely from a file reader node
            file_content = input_data.get("content", "")
            file_metadata = input_data.get("metadata", {})
        elif isinstance(input_data, str):
            # Input is a string, treat as content
            file_content = input_data
            file_metadata = {
                "filename": "unknown.txt",
                "type": "text/plain",
                "size": len(input_data)
            }
        
        if not file_content:
            return NodeResult(
                output={"error": "No valid file content found in input"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error="No valid file content found in input",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "File Transformer")
            )
        
        # Process file based on operation
        if operation == "convert":
            # Simple text conversion examples
            if output_format == "base64":
                # Convert to base64
                try:
                    if isinstance(file_content, str):
                        encoded = base64.b64encode(file_content.encode(encoding)).decode('ascii')
                    else:
                        encoded = base64.b64encode(file_content).decode('ascii')
                    
                    result = {
                        "content": encoded,
                        "metadata": {
                            "filename": file_metadata.get("filename", "unknown.txt"),
                            "type": "text/plain;base64",
                            "size": len(encoded),
                            "original_size": len(file_content) if isinstance(file_content, str) else len(file_content),
                            "encoding": "base64"
                        }
                    }
                except Exception as e:
                    result = {
                        "error": f"Base64 encoding failed: {str(e)}",
                        "original_content_type": type(file_content).__name__
                    }
            
            elif output_format == "text":
                # Ensure content is text
                try:
                    if not isinstance(file_content, str):
                        try:
                            text_content = file_content.decode(encoding)
                        except:
                            text_content = str(file_content)
                    else:
                        text_content = file_content
                    
                    result = {
                        "content": text_content,
                        "metadata": {
                            "filename": file_metadata.get("filename", "unknown.txt"),
                            "type": "text/plain",
                            "size": len(text_content),
                            "encoding": encoding
                        }
                    }
                except Exception as e:
                    result = {
                        "error": f"Text conversion failed: {str(e)}",
                        "original_content_type": type(file_content).__name__
                    }
            
            elif output_format == "json":
                # Convert to JSON if possible
                try:
                    if isinstance(file_content, str):
                        if file_content.strip().startswith(("{", "[")):
                            # Looks like JSON string, parse it
                            json_data = json.loads(file_content)
                            json_str = json.dumps(json_data, indent=2)
                        else:
                            # Try to convert text to JSON object
                            json_data = {"text": file_content}
                            json_str = json.dumps(json_data, indent=2)
                    else:
                        # Try to convert bytes to string then to JSON
                        try:
                            text = file_content.decode(encoding)
                            if text.strip().startswith(("{", "[")):
                                json_data = json.loads(text)
                            else:
                                json_data = {"content": text}
                        except:
                            json_data = {"content": str(file_content)}
                        
                        json_str = json.dumps(json_data, indent=2)
                    
                    result = {
                        "content": json_str,
                        "data": json_data,
                        "metadata": {
                            "filename": file_metadata.get("filename", "").replace(".", "") + ".json",
                            "type": "application/json",
                            "size": len(json_str)
                        }
                    }
                except Exception as e:
                    result = {
                        "error": f"JSON conversion failed: {str(e)}",
                        "original_content_type": type(file_content).__name__
                    }
        
        elif operation == "extract":
            # Extract metadata from file
            filename = file_metadata.get("filename", "unknown")
            file_type = file_metadata.get("type", "unknown")
            
            if not file_type or file_type == "unknown":
                # Try to guess mime type from filename
                file_type, _ = mimetypes.guess_type(filename)
            
            result = {
                "metadata": {
                    "filename": filename,
                    "extension": Path(filename).suffix if filename else "",
                    "basename": Path(filename).stem if filename else "",
                    "type": file_type,
                    "size": len(file_content) if isinstance(file_content, str) else len(file_content),
                    "encoding": encoding
                }
            }
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "File Transformer")
        )
    
    except Exception as e:
        logger.error(f"Error in File Transformer node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error", 
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "File Transformer")
        ) 
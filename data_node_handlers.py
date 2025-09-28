import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
import json
import re
import os
import base64
import mimetypes
from pathlib import Path

# Import handlers from dedicated files
from text_processor_node import handle_text_processor_node
from json_handler_node import handle_json_handler_node
from file_transformer_node import handle_file_transformer_node

logger = logging.getLogger("workflow_api")

# Export the imported handlers directly
__all__ = [
    "handle_text_processor_node",
    "handle_json_handler_node",
    "handle_file_transformer_node"
]

async def handle_text_processor_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for text_processor node type"""
    logger.info(f"Executing Text Processor node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "transform")
    transform_type = node_data.get("params", {}).get("transformType", "uppercase")
    pattern = node_data.get("params", {}).get("pattern", "")
    replacement = node_data.get("params", {}).get("replacement", "")
    extract_pattern = node_data.get("params", {}).get("extractPattern", "")
    split_delimiter = node_data.get("params", {}).get("splitDelimiter", ",")
    
    # Get input text
    input_text = inputs.get("input", "")
    if not isinstance(input_text, str):
        # Try to convert to string
        try:
            input_text = str(input_text)
        except Exception as e:
            return NodeResult(
                output={"error": f"Input is not a valid text: {str(e)}"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Input is not a valid text: {str(e)}",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "Text Processor")
            )
    
    result = {}
    result_text = input_text
    
    try:
        if operation == "transform":
            if transform_type == "uppercase":
                result_text = input_text.upper()
            elif transform_type == "lowercase":
                result_text = input_text.lower()
            elif transform_type == "capitalize":
                result_text = input_text.capitalize()
            elif transform_type == "title":
                result_text = input_text.title()
            elif transform_type == "strip":
                result_text = input_text.strip()
            elif transform_type == "replace":
                result_text = input_text.replace(pattern, replacement)
            elif transform_type == "regex_replace":
                result_text = re.sub(pattern, replacement, input_text)
            
            result = {
                "text": result_text,
                "operation": "transform",
                "transform_type": transform_type,
                "original_length": len(input_text),
                "new_length": len(result_text)
            }
        
        elif operation == "extract":
            if extract_pattern:
                matches = re.findall(extract_pattern, input_text)
                result = {
                    "matches": matches,
                    "count": len(matches),
                    "operation": "extract",
                    "pattern": extract_pattern
                }
            else:
                result = {
                    "matches": [],
                    "count": 0,
                    "operation": "extract",
                    "error": "No extraction pattern provided"
                }
        
        elif operation == "split":
            parts = input_text.split(split_delimiter)
            result = {
                "parts": parts,
                "count": len(parts),
                "operation": "split",
                "delimiter": split_delimiter
            }
        
        elif operation == "analyze":
            # Perform basic text analysis
            words = re.findall(r'\b\w+\b', input_text)
            sentences = re.split(r'[.!?]+', input_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            result = {
                "character_count": len(input_text),
                "word_count": len(words),
                "sentence_count": len(sentences),
                "line_count": input_text.count('\n') + 1,
                "operation": "analyze"
            }
        
        # Store result in workflow data for variable access
        var_name = node_data.get("params", {}).get("variableName", f"text_{node_id[:4]}")
        workflow_data[var_name] = result_text if operation == "transform" else result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Text Processor")
        )
    
    except Exception as e:
        logger.error(f"Error in Text Processor node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Text Processor")
        )

async def handle_json_handler_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any], 
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for json_handler node type"""
    logger.info(f"Executing JSON Handler node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "parse")
    path = node_data.get("params", {}).get("path", "")
    format_output = node_data.get("params", {}).get("formatOutput", False)
    default_value = node_data.get("params", {}).get("defaultValue", None)
    transform_keys = node_data.get("params", {}).get("transformKeys", [])
    
    # Get input data
    input_data = inputs.get("input", "")
    
    try:
        result = {}
        
        if operation == "parse":
            # Parse string to JSON
            if isinstance(input_data, str):
                parsed_json = json.loads(input_data)
                result = {
                    "data": parsed_json,
                    "operation": "parse",
                    "type": type(parsed_json).__name__
                }
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
                except:
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
                except:
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
        var_name = node_data.get("params", {}).get("variableName", f"json_{node_id[:4]}")
        result_value = result.get("data", result.get("value", result.get("string", result)))
        workflow_data[var_name] = result_value
        
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

async def handle_file_transformer_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for file_transformer node type"""
    logger.info(f"Executing File Transformer node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "convert")
    output_format = node_data.get("params", {}).get("outputFormat", "text")
    encoding = node_data.get("params", {}).get("encoding", "utf-8")
    
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
        var_name = node_data.get("params", {}).get("variableName", f"file_{node_id[:4]}")
        workflow_data[var_name] = result
        
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

async def handle_chat_file_reader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for chat_file_reader node type"""
    logger.info(f"Executing Chat File Reader node {node_id}")
    
    # Extract parameters
    file_type = node_data.get("params", {}).get("fileType", "all")
    max_file_size = node_data.get("params", {}).get("maxFileSize", 10)  # in MB
    selected_file = node_data.get("params", {}).get("selectedFile", "")
    
    # If input contains file data, use that instead of configured file
    input_data = inputs.get("input", None)
    if input_data and isinstance(input_data, dict) and "filename" in input_data:
        selected_file = input_data.get("filename", "")
        file_content = input_data.get("content", "")
        file_metadata = {
            "filename": selected_file,
            "size": len(file_content),
            "type": input_data.get("type", mimetypes.guess_type(selected_file)[0]),
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
                "type": mimetypes.guess_type(selected_file)[0],
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
    var_name = node_data.get("params", {}).get("variableName", f"file_{node_id[:4]}")
    result = {
        "content": file_content,
        "metadata": file_metadata,
        "filename": file_metadata.get("filename", None)
    }
    workflow_data[var_name] = result
    
    return NodeResult(
        output=result,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Chat File Reader")
    ) 
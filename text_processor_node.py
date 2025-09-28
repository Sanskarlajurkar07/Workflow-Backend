import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_text_processor_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for text_processor node type
    
    This node processes and manipulates text data with various operations.
    """
    logger.info(f"Executing Text Processor node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "transform")
    transform_type = node_data.get("params", {}).get("transformType", "uppercase")
    pattern = node_data.get("params", {}).get("pattern", "")
    replacement = node_data.get("params", {}).get("replacement", "")
    extract_pattern = node_data.get("params", {}).get("extractPattern", "")
    split_delimiter = node_data.get("params", {}).get("splitDelimiter", ",")
    variable_name = node_data.get("params", {}).get("variableName", f"processed_text_{node_id[:4]}")
    
    # Process variables in parameters
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if pattern and var_placeholder in pattern:
                pattern = pattern.replace(var_placeholder, str(value))
            if replacement and var_placeholder in replacement:
                replacement = replacement.replace(var_placeholder, str(value))
            if extract_pattern and var_placeholder in extract_pattern:
                extract_pattern = extract_pattern.replace(var_placeholder, str(value))
            if split_delimiter and var_placeholder in split_delimiter:
                split_delimiter = split_delimiter.replace(var_placeholder, str(value))
    
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
        workflow_data[variable_name] = result_text if operation == "transform" else result
        
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
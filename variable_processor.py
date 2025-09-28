"""
Variable processing system for workflow automation
"""
import re
import json
from typing import Dict, Any, Union, Optional

class VariableProcessor:
    def __init__(self):
        self.variable_pattern = r'\{\{([^}]+)\}\}'

    def process_variables(self, text: str, node_outputs: Dict[str, Any]) -> str:
        """Process all variables in the text using node outputs"""
        if not isinstance(text, str):
            return str(text) if text is not None else ""

        def replace_variable(match):
            var_path = match.group(1).strip()
            try:
                return self._get_variable_value(var_path, node_outputs)
            except Exception as e:
                return f"⚠️ Variable processing error: {str(e)}"

        return re.sub(self.variable_pattern, replace_variable, text)

    def _normalize_node_name(self, node_name: str, node_outputs: Dict[str, Any]) -> Optional[str]:
        """Normalize node name to match available outputs"""
        # Exact match first
        if node_name in node_outputs:
            return node_name
        
        # Try removing numeric suffixes and matching
        core_name = re.sub(r'[-_]\d+$', '', node_name)
        for output_key in node_outputs.keys():
            output_core = re.sub(r'[-_]\d+$', '', output_key)
            if core_name == output_core:
                return output_key
        
        # Advanced pattern matching
        for output_key in node_outputs.keys():
            # Handle input_0 → input_input0
            if node_name.startswith('input_') and 'input' in output_key:
                num_match = re.search(r'input[-_](\d+)$', node_name)
                if num_match:
                    num = num_match.group(1)
                    if output_key.endswith(num):
                        return output_key
            
            # Handle openai_0 → openai-0 or openai_0 → openai_input0
            if node_name.startswith('openai_') and ('openai' in output_key or 'ai' in output_key):
                num_match = re.search(r'openai[-_](\d+)$', node_name)
                if num_match:
                    num = num_match.group(1)
                    if output_key.endswith(num):
                        return output_key
            
            # Handle output_0 → output-0 or output_input0
            if node_name.startswith('output_') and ('output' in output_key or 'result' in output_key):
                num_match = re.search(r'output[-_](\d+)$', node_name)
                if num_match:
                    num = num_match.group(1)
                    if output_key.endswith(num):
                        return output_key
        
        return None

    def _get_variable_value(self, var_path: str, node_outputs: Dict[str, Any]) -> str:
        """Get the value of a variable from node outputs"""
        if '.' not in var_path:
            raise ValueError(f"Invalid variable format: {var_path}. Expected format: node_name.field")

        node_name, field = var_path.split('.', 1)
        
        # Normalize node name to match available outputs
        normalized_node_name = self._normalize_node_name(node_name, node_outputs)
        
        if not normalized_node_name:
            available_nodes = list(node_outputs.keys())
            raise ValueError(f"Node '{node_name}' not found. Available nodes: {available_nodes}")

        node_data = node_outputs[normalized_node_name]
        
        # Handle different node data types
        if isinstance(node_data, dict):
            # Try to get the requested field
            value = self._get_field_value(node_data, field)
            if value is not None:
                return self._format_value_by_type(value, field)
            else:
                available_fields = list(node_data.keys())
                raise ValueError(f"Field '{field}' not found in node '{node_name}'. Available fields: {available_fields}")
        else:
            # If node_data is not a dict, just return it as string
            return str(node_data)

    def _get_field_value(self, node_data: Dict[str, Any], field: str) -> Any:
        """Get field value with fallback logic"""
        # Direct field match
        if field in node_data:
            return node_data[field]
            
        # Try lowercase version
        field_lower = field.lower()
        if field_lower in node_data:
            return node_data[field_lower]
            
        # Field mapping for common cases
        field_mappings = {
            'text': ['output', 'content', 'response', 'value', 'result'],
            'output': ['text', 'content', 'response', 'value', 'result'],
            'content': ['output', 'text', 'response', 'value', 'result'],
            'response': ['output', 'content', 'text', 'value', 'result'],
            'value': ['output', 'content', 'text', 'response', 'result'],
            'result': ['output', 'content', 'text', 'response', 'value']
        }
        
        # Try field mappings
        if field in field_mappings:
            for alternative in field_mappings[field]:
                if alternative in node_data:
                    return node_data[alternative]
                    
        # Try with lowercase alternatives
        if field_lower in field_mappings:
            for alternative in field_mappings[field_lower]:
                if alternative in node_data:
                    return node_data[alternative]
        
        return None

    def _format_value_by_type(self, value: Any, field: str) -> str:
        """Format value based on its type and field name"""
        if value is None:
            return ""

        # Handle different field types
        if field in ['text', 'response', 'content', 'transcript', 'output', 'value', 'result']:
            return str(value)
        elif field in ['json', 'metadata', 'full_response']:
            return json.dumps(value, indent=2) if isinstance(value, (dict, list)) else str(value)
        elif field in ['image', 'audio', 'file']:
            if isinstance(value, dict) and 'url' in value:
                return value['url']
            return str(value)
        
        # Default handling
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def validate_variable_usage(self, text: str, available_variables: Dict[str, Dict[str, str]]) -> Optional[str]:
        """Validate variable usage in text"""
        if not isinstance(text, str):
            return None

        variables = re.findall(self.variable_pattern, text)
        for var in variables:
            var = var.strip()
            if '.' not in var:
                return f"Invalid variable format: {var}. Expected format: node_name.field"

            node_name, field = var.split('.', 1)
            
            # Try to normalize the node name
            normalized_name = None
            for available_name in available_variables.keys():
                if (node_name == available_name or 
                    node_name.replace('_', '-') == available_name or
                    node_name.replace('-', '_') == available_name):
                    normalized_name = available_name
                    break
            
            if not normalized_name:
                return f"Node '{node_name}' not found"

            node_info = available_variables[normalized_name]
            if 'type' in node_info and field != node_info['type'].lower():
                return f"Invalid field '{field}' for node '{node_name}'. Expected: {node_info['type'].lower()}"

        return None

def process_node_variables(text: str, node_outputs: Dict[str, Any]) -> str:
    """Process variables in text using node outputs"""
    processor = VariableProcessor()
    return processor.process_variables(text, node_outputs)

def normalize_node_output(output: Union[Dict[str, Any], Any], node_type: str = None) -> Dict[str, Any]:
    """
    Normalize node output to ensure consistent structure and field access.
    
    Args:
        output (dict or any): The output to normalize
        node_type (str, optional): Type of node for specific normalization
    
    Returns:
        dict: Normalized output with consistent keys
    """
    # If output is not a dictionary, convert it to a dictionary
    if not isinstance(output, dict):
        output = {"output": str(output) if output is not None else ""}
    
    # Ensure basic output fields exist
    normalized = {
        "output": output.get("output", output.get("text", output.get("content", output.get("value", "")))),
        "content": output.get("content", output.get("output", output.get("text", output.get("value", "")))),
        "value": output.get("value", output.get("output", output.get("content", output.get("text", "")))),
        "text": output.get("text", output.get("output", output.get("content", output.get("value", ""))))
    }
    
    # Copy all other fields from original output
    for key, value in output.items():
        if key not in normalized:
            normalized[key] = value
    
    # Special handling for input and output nodes
    if node_type == "input":
        # Ensure input nodes have consistent naming
        input_type_mapping = {
            "text": "text",
            "image": "image",
            "audio": "audio",
            "file": "file",
            "json": "json"
        }
        
        # Add type-specific field if it exists
        for type_name, field_name in input_type_mapping.items():
            if field_name in output:
                normalized[type_name] = output[field_name]
    
    elif node_type == "output":
        # Ensure output nodes have consistent naming
        normalized["result"] = normalized.get("output")
    
    return normalized

def validate_variables(text: str, available_variables: Dict[str, Dict[str, str]]) -> Optional[str]:
    """Validate variable usage in text"""
    processor = VariableProcessor()
    return processor.validate_variable_usage(text, available_variables)

def extract_variables_from_text(text: str) -> list:
    """Extract all variables from text in {{variable}} format"""
    if not text or not isinstance(text, str):
        return []
    
    pattern = r'\{\{([^}]+)\}\}'
    matches = re.findall(pattern, text)
    return [match.strip() for match in matches]

def normalize_node_output(node_output: Any, node_type: str = None) -> Dict[str, Any]:
    """
    Normalize node output to ensure consistent field access
    
    Args:
        node_output: Raw output from node execution
        node_type: Type of the node (for type-specific normalization)
    
    Returns:
        Normalized output dictionary with standard fields
    """
    if isinstance(node_output, dict):
        # Already a dictionary, ensure standard fields exist
        normalized = dict(node_output)
        
        # Ensure 'output' field exists
        if 'output' not in normalized:
            # Try to find the main content field
            content_fields = ['content', 'text', 'response', 'result', 'value', 'data']
            for field in content_fields:
                if field in normalized:
                    normalized['output'] = normalized[field]
                    break
            else:
                # If no content field found, use the first non-metadata field
                for key, value in normalized.items():
                    if key not in ['type', 'status', 'execution_time', 'node_id', 'node_name', 'error']:
                        normalized['output'] = value
                        break
        
        # For AI nodes, ensure 'response' field exists
        if node_type and any(ai_type in node_type.lower() for ai_type in ['openai', 'anthropic', 'gemini', 'cohere', 'ai']):
            if 'response' not in normalized and 'output' in normalized:
                normalized['response'] = normalized['output']
        
        # Ensure text field exists for string outputs
        if 'text' not in normalized and 'output' in normalized:
            normalized['text'] = str(normalized['output'])
        
        return normalized
    else:
        # Convert direct value to dictionary with all standard fields
        return {
            'output': node_output,
            'value': node_output,
            'text': str(node_output) if node_output is not None else '',
            'content': str(node_output) if node_output is not None else '',
            'data': node_output,
            'result': node_output
        } 
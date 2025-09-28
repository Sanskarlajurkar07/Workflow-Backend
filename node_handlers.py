import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from models.workflow import NodeResult
import re

# Import all the node handlers
from new_node_handlers import handle_chat_memory_node, handle_data_collector_node, handle_chat_file_reader_node
from ai_node_handlers import handle_ai_tools_node, handle_spark_layer_node, handle_ai_task_executor_node
from integration_node_handlers import (
    handle_gmail_trigger_node, 
    handle_outlook_trigger_node, 
    handle_notification_node,
    handle_crm_enricher_node
)
from data_node_handlers import (
    handle_text_processor_node,
    handle_json_handler_node,
    handle_file_transformer_node
)
from api_loader_node import handle_api_loader_node
from youtube_loader_node import handle_youtube_loader_node
from arxiv_loader_node import handle_arxiv_loader_node
from url_loader_node import handle_url_loader_node
from rss_feed_loader_node import handle_rss_feed_loader_node
from wikipedia_search_node import handle_wikipedia_search_node
from google_drive_node import handle_google_drive_node
from document_to_text_node import handle_document_to_text_node
from file_save_node import handle_file_save_node
from sharing_node import handle_share_object_node
from routers.audio_processor import handle_audio_processor_node
from routers.image_processor import handle_image_processor_node
from github_node import handle_github_node
from ai_providers_node import (
    handle_openai_node,
    handle_anthropic_node, 
    handle_gemini_node,
    handle_cohere_node,
    handle_perplexity_node,
    handle_xai_node,
    handle_azure_node
)
from variable_processor import process_node_variables, normalize_node_output, validate_variables

logger = logging.getLogger("workflow_api")

# Define handle_input_node before NODE_HANDLERS dictionary
async def handle_input_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None  # Added request to match other handlers
) -> NodeResult:
    """Handle input node execution with enhanced output structure"""
    logger.info(f"Executing input node {node_id}")
    
    # Get node parameters
    params = node_data.get("params", {})
    
    # Normalize node name: prefer user-defined name, fallback to standardized format
    node_name = params.get("nodeName")
    if not node_name:
        # Extract number from node_id, handling both input-0 and input_0 formats
        match = re.search(r'input[-_](\d+)', node_id)
        node_num = match.group(1) if match else '0'
        node_name = f"input_{node_num}"
    
    input_type = params.get("type", "Text")
    
    # Get the input value
    input_value = inputs.get("input", "")
    
    # Convert input value to string if needed
    if input_value is not None:
        input_str = str(input_value)
    else:
        input_str = ""
    
    # Map input types to field names (following frontend AutocompleteInput.tsx logic)
    type_field_mapping = {
        "Text": "text",
        "Image": "image", 
        "Audio": "audio",
        "File": "file",
        "JSON": "json",
        "Formatted Text": "text"
    }
    
    # Get the type-specific field name
    type_field = type_field_mapping.get(input_type, "text").lower()
    
    # Create output with type-specific field
    output_dict = {
        "output": input_str,        # Primary output field
        "content": input_str,       # Content access
        "value": input_str,         # Generic value access
        "type": input_type,
        "node_name": node_name,
        "input_raw": input_value    # Original input value
    }
    
    # Add the type-specific field that the frontend expects
    output_dict[type_field] = input_str
    
    # Also add common aliases for compatibility
    output_dict["text"] = input_str  # Always provide text access
    
    # Create normalized output
    result = normalize_node_output(output_dict, "input")
    
    logger.info(f"Input node {node_id} completed. Type: {input_type}, Type field: {type_field}, Output: '{input_str}'")
    logger.info(f"Input node {node_id} output fields: {list(result.keys())}")
    
    return NodeResult(
        output=result,
        type=input_type.lower(),
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_name
    )

# Define handle_output_node function
async def handle_output_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    """Handle output node execution with variable processing"""
    logger.info(f"Executing output node {node_id}")
    
    # Get node parameters
    params = node_data.get("params", {})
    node_name = params.get("nodeName", f"output_{node_id.split('-')[-1] if '-' in node_id else '0'}")
    field_name = params.get("fieldName", node_name)
    output_template = params.get("output", "")
    output_type = params.get("type", "Text")
    
    # Get current node outputs for variable processing
    node_outputs = getattr(request, 'node_outputs', {}) if request else {}
    
    logger.info(f"Output node processing template: '{output_template}'")
    logger.info(f"Available node outputs: {list(node_outputs.keys())}")
    
    # Process variables in the output template
    processed_output = process_node_variables(output_template, node_outputs)
    
    # If no template provided or template didn't change, try to get input directly
    if not processed_output or processed_output == output_template:
        # Check if there's a direct input connection
        direct_input = inputs.get("input", "")
        if direct_input:
            processed_output = str(direct_input)
            logger.info(f"Using direct input: '{processed_output}'")
        elif not processed_output:
            processed_output = f"No output template configured for {node_name}"
    
    # Create normalized output
    result = normalize_node_output({
        "output": processed_output,
        "value": processed_output,
        "text": processed_output,
        "content": processed_output,
        "field_name": field_name,
        "type": output_type,
        "template": output_template,
        "processed_template": processed_output
    }, "output")
    
    logger.info(f"Output node {node_id} completed. Final output: '{processed_output}'")
    
    return NodeResult(
        output=result,
        type=output_type.lower(),
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_name
    )

# Dictionary mapping node types to their handler functions
NODE_HANDLERS: Dict[str, Callable] = {
    "chat_memory": handle_chat_memory_node,
    "data_collector": handle_data_collector_node,
    "chat_file_reader": handle_chat_file_reader_node,
    "ai_tools": handle_ai_tools_node,
    "spark_layer": handle_spark_layer_node,
    "ai_task_executor": handle_ai_task_executor_node,
    "gmail_trigger": handle_gmail_trigger_node,
    "outlook_trigger": handle_outlook_trigger_node,
    "notification": handle_notification_node,
    "crm_enricher": handle_crm_enricher_node,
    "text_processor": handle_text_processor_node,
    "json_handler": handle_json_handler_node,
    "file_transformer": handle_file_transformer_node,
    "api_loader": handle_api_loader_node,
    "youtube_loader": handle_youtube_loader_node,
    "arxiv_loader": handle_arxiv_loader_node,
    "url_loader": handle_url_loader_node,
    "rss_feed_loader": handle_rss_feed_loader_node,
    "wikipedia_loader": handle_wikipedia_search_node,
    "google_drive": handle_google_drive_node,
    "document_to_text": handle_document_to_text_node,
    "file_save": handle_file_save_node,
    "share_object": handle_share_object_node,
    "audio-processor": handle_audio_processor_node,
    "image-processor": handle_image_processor_node,
    "openai": handle_openai_node,
    "anthropic": handle_anthropic_node,
    "gemini": handle_gemini_node,
    "cohere": handle_cohere_node,
    "perplexity": handle_perplexity_node,
    "xai": handle_xai_node,
    "azure": handle_azure_node,
    "github": handle_github_node,
    "input": handle_input_node,
    "output": handle_output_node
}

async def handle_node(
    node_id: str,
    node_type: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    request=None
) -> NodeResult:
    """
    Handle a node execution based on its type.
    
    Args:
        node_id: The ID of the node
        node_type: The type of the node
        node_data: The node's data
        inputs: The inputs to the node
        workflow_data: The workflow data
        request: The request object (optional)
    
    Returns:
        NodeResult: The result of the node execution
    """
    start_time = datetime.now().timestamp()
    
    # Diagnostic logging to debug the NameError issue
    logger.info(f"DIAGNOSTIC: In handle_node for node_id: {node_id}, node_type: '{node_type}'")
    logger.info(f"DIAGNOSTIC: NODE_HANDLERS available keys: {list(NODE_HANDLERS.keys())}")
    if "input" in NODE_HANDLERS:
        logger.info(f"DIAGNOSTIC: Type of NODE_HANDLERS['input']: {type(NODE_HANDLERS['input'])}")
        logger.info(f"DIAGNOSTIC: Is NODE_HANDLERS['input'] callable: {callable(NODE_HANDLERS['input'])}")
        if hasattr(NODE_HANDLERS['input'], '__name__'):
            logger.info(f"DIAGNOSTIC: Name of NODE_HANDLERS['input']: {NODE_HANDLERS['input'].__name__}")
        else:
            logger.info("DIAGNOSTIC: NODE_HANDLERS['input'] does not have a __name__ attribute.")
    else:
        logger.warning("DIAGNOSTIC: Critical: Handler for 'input' not found in NODE_HANDLERS at the point of access!")
    
    # Get the handler function for the node type
    handler = NODE_HANDLERS.get(node_type)
    
    if handler:
        try:
            # Execute the handler function
            if request:
                result = await handler(node_id, node_data, inputs, workflow_data, start_time, request)
            else:
                result = await handler(node_id, node_data, inputs, workflow_data, start_time)
            return result
        except Exception as e:
            logger.error(f"Error executing node {node_id} of type {node_type}: {str(e)}", exc_info=True)
            return NodeResult(
                node_id=node_id,
                status="error",
                message=f"Error executing node: {str(e)}",
                output={"error": f"Error executing node: {str(e)}"},
                data=None,
                execution_time=datetime.now().timestamp() - start_time
            )
    else:
        logger.error(f"No handler found for node type: {node_type}")
        return NodeResult(
            node_id=node_id,
            status="error",
            message=f"No handler found for node type: {node_type}",
            output={"error": f"No handler found for node type: {node_type}"},
            data=None,
            execution_time=datetime.now().timestamp() - start_time
        )

async def register_node_definitions(request: Any) -> Dict[str, Any]:
    """Register all available node definitions in the system"""
    
    # This function would typically load detailed node definitions from a database
    # or configuration file. For this implementation, we'll return a simple dictionary.
    
    # Basic node categories
    categories = {
        "AI & Language": {
            "icon": "Sparkles",
            "color": "purple",
            "description": "Nodes for AI, language processing, and ML tasks"
        },
        "Data Processing": {
            "icon": "Database",
            "color": "blue",
            "description": "Nodes for data transformation and manipulation"
        },
        "Integrations": {
            "icon": "Plug",
            "color": "green",
            "description": "Nodes for external service integrations"
        },
        "Flow Control": {
            "icon": "GitBranch",
            "color": "orange",
            "description": "Nodes for controlling workflow execution"
        },
        "Input/Output": {
            "icon": "ArrowLeftRight",
            "color": "gray",
            "description": "Nodes for workflow input and output"
        },
        "Media Processing": {
            "icon": "Music",
            "color": "pink",
            "description": "Nodes for processing media files"
        }
    }
    
    # Define basic node types
    node_definitions = {
        # Google Drive node
        "google_drive": {
            "name": "Google Drive",
            "description": "Connect to Google Drive for file operations",
            "category": "Integrations",
            "inputs": [
                {"name": "input", "type": "any", "description": "Input data from previous nodes", "optional": True}
            ],
            "outputs": [
                {"name": "files", "type": "array", "description": "Files from Google Drive"},
                {"name": "auth_info", "type": "object", "description": "Authentication information"}
            ],
            "configuration": [
                {"name": "operation", "type": "select", "description": "Operation to perform", 
                 "options": ["list_files", "get_file", "upload_file", "create_folder", "delete_file", "search_files"]},
                {"name": "folderId", "type": "string", "description": "Folder ID (root by default)", "default": "root", "optional": True, "showVariableInsertButton": True},
                {"name": "fileId", "type": "string", "description": "File ID for operations on specific files", "optional": True, "showVariableInsertButton": True},
                {"name": "query", "type": "string", "description": "Query string for search", "optional": True, "showVariableInsertButton": True},
                {"name": "filePath", "type": "string", "description": "Path to file for upload", "optional": True, "showVariableInsertButton": True},
                {"name": "fileName", "type": "string", "description": "Name for files or folders", "optional": True, "showVariableInsertButton": True},
                {"name": "fileMimeType", "type": "string", "description": "MIME type for upload", "optional": True, "showVariableInsertButton": True},
                {"name": "pageSize", "type": "number", "description": "Maximum number of results", "default": 10, "showVariableInsertButton": True},
                {"name": "clientId", "type": "string", "description": "Google API Client ID", "showVariableInsertButton": True},
                {"name": "clientSecret", "type": "string", "description": "Google API Client Secret", "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "google_drive", "showVariableInsertButton": True}
            ]
        },
        
        # AI-related nodes
        "ai_tools": {
            "name": "AI Tools",
            "description": "Use various AI models for text generation and completion",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for the AI model"},
                {"name": "context", "type": "string", "description": "Additional context for the AI model", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from the AI model"},
                {"name": "model", "type": "string", "description": "The model used"},
                {"name": "input_tokens", "type": "number", "description": "Number of input tokens processed"},
                {"name": "output_tokens", "type": "number", "description": "Number of output tokens generated"}
            ],
            "configuration": [
                {"name": "provider", "type": "select", "description": "AI provider", "options": ["openai", "anthropic", "gemini", "cohere"]},
                {"name": "model", "type": "select", "description": "AI model to use", "dynamicOptions": "models"},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-1.0)", "default": 0.7},
                {"name": "systemPrompt", "type": "text", "description": "System instructions", "optional": True},
                {"name": "promptTemplate", "type": "text", "description": "Template for prompt", "default": "{{input}}"},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "ai_result", "showVariableInsertButton": True}
            ]
        },
        
        "spark_layer": {
            "name": "Spark Layer",
            "description": "Create and work with vector embeddings",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Text to process"}
            ],
            "outputs": [
                {"name": "embedding", "type": "array", "description": "Vector embedding"},
                {"name": "dimension", "type": "number", "description": "Embedding dimension"}
            ],
            "configuration": [
                {"name": "mode", "type": "select", "description": "Operation mode", 
                 "options": ["text_to_embedding", "embedding_similarity", "semantic_search"]},
                {"name": "provider", "type": "select", "description": "Embedding provider", 
                 "options": ["openai", "cohere", "tensorflow", "huggingface"]},
                {"name": "model", "type": "select", "description": "Embedding model", 
                 "dynamicOptions": "embedding_models"},
                {"name": "inputFormat", "type": "select", "description": "Input format", 
                 "options": ["single", "batch"]},
                {"name": "dimension", "type": "number", "description": "Vector dimension", "default": 1536},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "embedding", "showVariableInsertButton": True}
            ]
        },
        
        "ai_task_executor": {
            "name": "AI Task Executor", 
            "description": "Execute specific AI tasks like summarization, sentiment analysis, etc.",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for processing"}
            ],
            "outputs": [
                {"name": "result", "type": "object", "description": "Task result"},
                {"name": "task_type", "type": "string", "description": "Task type that was executed"}
            ],
            "configuration": [
                {"name": "taskType", "type": "select", "description": "Task to execute", 
                 "options": ["text_summarization", "sentiment_analysis", "content_generation", "translation", "text_classification"]},
                {"name": "provider", "type": "select", "description": "AI provider", 
                 "options": ["openai", "anthropic", "gemini", "cohere"]},
                {"name": "model", "type": "select", "description": "AI model", "dynamicOptions": "models"},
                {"name": "taskConfig", "type": "object", "description": "Task-specific configuration"},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "task_result", "showVariableInsertButton": True}
            ]
        },
        
        "chat_memory": {
            "name": "Chat Memory",
            "description": "Store and manage chat history for conversations",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "any", "description": "New messages to add to memory"}
            ],
            "outputs": [
                {"name": "history", "type": "array", "description": "Complete chat history"},
                {"name": "recent", "type": "array", "description": "Recent messages"},
                {"name": "context", "type": "string", "description": "Formatted context string"}
            ],
            "configuration": [
                {"name": "memoryType", "type": "select", "description": "Memory management type", 
                 "options": ["token_buffer", "message_buffer", "full", "formatted_full_raw"]},
                {"name": "memorySize", "type": "number", "description": "Number of tokens/messages to keep", "default": 50},
                {"name": "variableName", "type": "string", "description": "Variable name for memory", "default": "chat_memory", "showVariableInsertButton": True}
            ]
        },
        
        # Data processing nodes
        "data_collector": {
            "name": "Data Collector",
            "description": "Collect structured data from user inputs",
            "category": "Data Processing",
            "inputs": [],
            "outputs": [
                {"name": "collected_data", "type": "object", "description": "Collected data as key-value pairs"},
                {"name": "raw_inputs", "type": "array", "description": "Raw input events"}
            ],
            "configuration": [
                {"name": "query", "type": "string", "description": "Query to prompt user", "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "Detailed instruction prompt", "showVariableInsertButton": True},
                {"name": "fields", "type": "array", "description": "Fields to collect", 
                 "items": {"type": "object", "showVariableInsertButton": True}},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "collected_data", "showVariableInsertButton": True}
            ]
        },
        
        "chat_file_reader": {
            "name": "Chat File Reader",
            "description": "Read and process files uploaded in chat",
            "category": "Data Processing",
            "inputs": [
                {"name": "input", "type": "any", "description": "File data if provided dynamically", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "File content"},
                {"name": "metadata", "type": "object", "description": "File metadata"},
                {"name": "filename", "type": "string", "description": "File name"}
            ],
            "configuration": [
                {"name": "fileType", "type": "select", "description": "File type filter", 
                 "options": ["all", "text", "image", "pdf", "csv", "json"]},
                {"name": "maxFileSize", "type": "number", "description": "Maximum file size in MB", "default": 10},
                {"name": "selectedFile", "type": "string", "description": "Predefined file to read", "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "file_data", "showVariableInsertButton": True}
            ]
        },
        
        "text_processor": {
            "name": "Text Processor",
            "description": "Process and transform text data",
            "category": "Data Processing",
            "inputs": [
                {"name": "input", "type": "string", "description": "Text to process"}
            ],
            "outputs": [
                {"name": "text", "type": "string", "description": "Processed text"},
                {"name": "operation", "type": "string", "description": "Operation performed"}
            ],
            "configuration": [
                {"name": "operation", "type": "select", "description": "Text operation", 
                 "options": ["transform", "extract", "split", "analyze"]},
                {"name": "transformType", "type": "select", "description": "Transformation type", 
                 "options": ["uppercase", "lowercase", "capitalize", "title", "strip", "replace", "regex_replace"]},
                {"name": "pattern", "type": "string", "description": "Pattern to find", "showVariableInsertButton": True},
                {"name": "replacement", "type": "string", "description": "Replacement text", "showVariableInsertButton": True},
                {"name": "extractPattern", "type": "string", "description": "Regex pattern for extraction", "showVariableInsertButton": True},
                {"name": "splitDelimiter", "type": "string", "description": "Delimiter for splitting", "default": ",", "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "processed_text", "showVariableInsertButton": True}
            ]
        },
        
        "json_handler": {
            "name": "JSON Handler",
            "description": "Process and manipulate JSON data",
            "category": "Data Processing",
            "inputs": [
                {"name": "input", "type": "any", "description": "JSON data or string to process"}
            ],
            "outputs": [
                {"name": "data", "type": "object", "description": "Processed JSON data"}
            ],
            "configuration": [
                {"name": "operation", "type": "select", "description": "JSON operation", 
                 "options": ["parse", "stringify", "extract", "transform"]},
                {"name": "path", "type": "string", "description": "JSON path for extraction (e.g., data.users.0.name)", "showVariableInsertButton": True},
                {"name": "formatOutput", "type": "boolean", "description": "Format JSON output for readability", "default": False},
                {"name": "defaultValue", "type": "any", "description": "Default value if path not found", "showVariableInsertButton": True},
                {"name": "transformKeys", "type": "array", "description": "Key transformation mappings", "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "json_data", "showVariableInsertButton": True}
            ]
        },
        
        "file_transformer": {
            "name": "File Transformer",
            "description": "Transform and convert file data between formats",
            "category": "Data Processing",
            "inputs": [
                {"name": "input", "type": "any", "description": "File data to transform"}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Transformed content"},
                {"name": "metadata", "type": "object", "description": "File metadata"}
            ],
            "configuration": [
                {"name": "operation", "type": "select", "description": "File operation", 
                 "options": ["convert", "extract"]},
                {"name": "outputFormat", "type": "select", "description": "Output format", 
                 "options": ["text", "base64", "json"]},
                {"name": "encoding", "type": "string", "description": "Text encoding", "default": "utf-8"},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "transformed_file", "showVariableInsertButton": True}
            ]
        },
        
        # Integration nodes
        "gmail_trigger": {
            "name": "Gmail Trigger",
            "description": "Trigger workflow based on Gmail events",
            "category": "Integrations",
            "inputs": [],
            "outputs": [
                {"name": "emails", "type": "array", "description": "Retrieved emails"},
                {"name": "count", "type": "number", "description": "Number of emails found"}
            ],
            "configuration": [
                {"name": "triggerType", "type": "select", "description": "Trigger type", 
                 "options": ["new_email", "email_with_attachment", "email_with_label"]},
                {"name": "labels", "type": "array", "description": "Gmail labels to filter by", "default": ["INBOX"]},
                {"name": "filter", "type": "string", "description": "Additional filter criteria", "showVariableInsertButton": True},
                {"name": "maxResults", "type": "number", "description": "Maximum emails to retrieve", "default": 10},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "gmail_emails", "showVariableInsertButton": True}
            ]
        },
        
        "outlook_trigger": {
            "name": "Outlook Trigger",
            "description": "Trigger workflow based on Outlook events",
            "category": "Integrations",
            "inputs": [],
            "outputs": [
                {"name": "items", "type": "array", "description": "Retrieved items (emails/events)"},
                {"name": "count", "type": "number", "description": "Number of items found"}
            ],
            "configuration": [
                {"name": "triggerType", "type": "select", "description": "Trigger type", 
                 "options": ["new_email", "calendar_event", "task_updated"]},
                {"name": "folder", "type": "string", "description": "Outlook folder to monitor", "default": "Inbox", "showVariableInsertButton": True},
                {"name": "filter", "type": "string", "description": "Filter criteria", "showVariableInsertButton": True},
                {"name": "maxResults", "type": "number", "description": "Maximum items to retrieve", "default": 10},
                {"name": "includeAttachments", "type": "boolean", "description": "Include attachments in results", "default": False},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "outlook_items", "showVariableInsertButton": True}
            ]
        },
        
        "notification": {
            "name": "Notification",
            "description": "Send notifications through various channels",
            "category": "Integrations",
            "inputs": [
                {"name": "input", "type": "string", "description": "Message content to include in notification", "optional": True}
            ],
            "outputs": [
                {"name": "sent", "type": "boolean", "description": "Whether notification was sent"},
                {"name": "type", "type": "string", "description": "Notification type"}
            ],
            "configuration": [
                {"name": "notificationType", "type": "select", "description": "Notification channel", 
                 "options": ["email", "slack", "webhook", "sms"]},
                {"name": "recipients", "type": "array", "description": "Recipients (emails, channels, etc.)", "showVariableInsertButton": True},
                {"name": "subject", "type": "string", "description": "Subject line", "showVariableInsertButton": True},
                {"name": "message", "type": "text", "description": "Notification message template", "showVariableInsertButton": True},
                {"name": "priority", "type": "select", "description": "Notification priority", 
                 "options": ["low", "normal", "high"]},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "notification_result", "showVariableInsertButton": True}
            ]
        },
        
        "crm_enricher": {
            "name": "CRM Enricher",
            "description": "Enrich contact and company data",
            "category": "Integrations",
            "inputs": [
                {"name": "input", "type": "any", "description": "Contact/company identifier to enrich"}
            ],
            "outputs": [
                {"name": "contact", "type": "object", "description": "Enriched contact data"},
                {"name": "company", "type": "object", "description": "Enriched company data"}
            ],
            "configuration": [
                {"name": "crmType", "type": "select", "description": "CRM type", 
                 "options": ["generic", "salesforce", "hubspot", "zoho"]},
                {"name": "enrichmentType", "type": "select", "description": "Type of enrichment", 
                 "options": ["contact", "company"]},
                {"name": "dataSources", "type": "array", "description": "Data sources to use", 
                 "default": ["internal"], "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "enriched_data", "showVariableInsertButton": True}
            ]
        },
        
        # Basic flow nodes
        "input": {
            "name": "Input",
            "description": "Workflow input node",
            "category": "Input/Output",
            "inputs": [],
            "outputs": [
                {"name": "output", "type": "any", "description": "Workflow input data"}
            ],
            "configuration": [
                {"name": "type", "type": "string", "description": "Input type", "default": "text"},
                {"name": "variableName", "type": "string", "description": "Variable name for input", "default": "input", "showVariableInsertButton": True}
            ]
        },
        
        "output": {
            "name": "Output",
            "description": "Workflow output node",
            "category": "Input/Output",
            "inputs": [
                {"name": "input", "type": "any", "description": "Data to output"}
            ],
            "outputs": [],
            "configuration": [
                {"name": "type", "type": "string", "description": "Output type", "default": "text"},
                {"name": "variableName", "type": "string", "description": "Variable name for output", "default": "output", "showVariableInsertButton": True}
            ]
        },
        
        # Media processing nodes
        "audio-processor": {
            "name": "Audio Processor",
            "description": "Process audio files and perform operations like transcription",
            "category": "Media Processing",
            "inputs": [
                {"name": "input", "type": "any", "description": "Audio file data to process"}
            ],
            "outputs": [
                {"name": "output", "type": "object", "description": "Processed audio result"},
                {"name": "text", "type": "string", "description": "Transcribed text if applicable"}
            ],
            "configuration": [
                {"name": "operation", "type": "select", "description": "Audio operation to perform", 
                 "options": ["transcribe", "analyze", "detect_language"], "showVariableInsertButton": True},
                {"name": "model", "type": "select", "description": "AI model to use", 
                 "options": ["whisper-1", "base", "small"], "showVariableInsertButton": True},
                {"name": "language", "type": "string", "description": "Language code (optional)", "optional": True, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Model temperature", "default": 0, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "audio_processor", "showVariableInsertButton": True}
            ]
        },
        
        "image-processor": {
            "name": "Image Processor",
            "description": "Process images and perform operations like OCR and image analysis",
            "category": "Media Processing",
            "inputs": [
                {"name": "input", "type": "any", "description": "Image file data to process"}
            ],
            "outputs": [
                {"name": "output", "type": "object", "description": "Processed image result"},
                {"name": "text", "type": "string", "description": "Extracted text if applicable"}
            ],
            "configuration": [
                {"name": "mode", "type": "select", "description": "Image processing mode", 
                 "options": ["image-to-text", "analyze", "detect_objects"], "showVariableInsertButton": True},
                {"name": "model", "type": "select", "description": "AI model to use", 
                 "options": ["gpt-4-vision", "llava", "ocr-default"], "showVariableInsertButton": True},
                {"name": "system", "type": "string", "description": "System prompt for vision models", "optional": True, "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens for response", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Model temperature", "default": 0, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "image_processor", "showVariableInsertButton": True}
            ]
        },
        
        # AI provider nodes with enhanced variable support
        "openai": {
            "name": "OpenAI",
            "description": "Use OpenAI's GPT models for text generation and completion",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for the AI model", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from OpenAI"},
                {"name": "model", "type": "string", "description": "The OpenAI model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "OpenAI model to use", 
                 "options": ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-2.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "OpenAI API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "openai_result", "showVariableInsertButton": True}
            ]
        },
        
        "anthropic": {
            "name": "Anthropic Claude",
            "description": "Use Anthropic's Claude models for advanced text generation",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Claude", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Claude"},
                {"name": "model", "type": "string", "description": "The Claude model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Claude model to use", 
                 "options": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-1.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "Anthropic API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "anthropic_result", "showVariableInsertButton": True}
            ]
        },
        
        "gemini": {
            "name": "Google Gemini",
            "description": "Use Google's Gemini models for multimodal AI capabilities",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Gemini", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Gemini"},
                {"name": "model", "type": "string", "description": "The Gemini model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Gemini model to use", 
                 "options": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro", "gemini-pro-vision"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-1.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "Google API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "gemini_result", "showVariableInsertButton": True}
            ]
        },
        
        "cohere": {
            "name": "Cohere",
            "description": "Use Cohere's language models for text generation and analysis",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Cohere", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Cohere"},
                {"name": "model", "type": "string", "description": "The Cohere model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Cohere model to use", 
                 "options": ["command-r-plus", "command-r", "command", "command-light", "command-nightly"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-5.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "Cohere API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "cohere_result", "showVariableInsertButton": True}
            ]
        },
        
        "perplexity": {
            "name": "Perplexity",
            "description": "Use Perplexity's models for research-backed AI responses",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Perplexity", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Perplexity"},
                {"name": "model", "type": "string", "description": "The Perplexity model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Perplexity model to use", 
                 "options": ["llama-3.1-sonar-small-128k-online", "llama-3.1-sonar-large-128k-online", "llama-3.1-sonar-huge-128k-online"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-2.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "Perplexity API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "perplexity_result", "showVariableInsertButton": True}
            ]
        },
        
        "xai": {
            "name": "xAI Grok",
            "description": "Use xAI's Grok models for witty and insightful responses",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Grok", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Grok"},
                {"name": "model", "type": "string", "description": "The Grok model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Grok model to use", 
                 "options": ["grok-beta", "grok-2", "grok-2-mini"]},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-2.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "xAI API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "xai_result", "showVariableInsertButton": True}
            ]
        },
        
        "azure": {
            "name": "Azure OpenAI",
            "description": "Use Microsoft Azure OpenAI Service for enterprise AI",
            "category": "AI & Language",
            "inputs": [
                {"name": "input", "type": "string", "description": "Input text for Azure OpenAI", "optional": True}
            ],
            "outputs": [
                {"name": "content", "type": "string", "description": "Generated text from Azure OpenAI"},
                {"name": "model", "type": "string", "description": "The Azure OpenAI model used"},
                {"name": "usage", "type": "object", "description": "Token usage information"}
            ],
            "configuration": [
                {"name": "model", "type": "select", "description": "Azure OpenAI model to use", 
                 "options": ["gpt-4", "gpt-4-32k", "gpt-4-turbo", "gpt-35-turbo", "gpt-35-turbo-16k"]},
                {"name": "deploymentName", "type": "string", "description": "Azure deployment name", "showVariableInsertButton": True},
                {"name": "endpoint", "type": "string", "description": "Azure OpenAI endpoint URL", "showVariableInsertButton": True},
                {"name": "apiVersion", "type": "string", "description": "API version", "default": "2024-02-15-preview", "showVariableInsertButton": True},
                {"name": "system", "type": "text", "description": "System instructions", "optional": True, "showVariableInsertButton": True},
                {"name": "prompt", "type": "text", "description": "User prompt template", "showVariableInsertButton": True},
                {"name": "maxTokens", "type": "number", "description": "Maximum tokens to generate", "default": 1000, "showVariableInsertButton": True},
                {"name": "temperature", "type": "number", "description": "Creativity level (0.0-2.0)", "default": 0.7, "showVariableInsertButton": True},
                {"name": "apiKey", "type": "password", "description": "Azure OpenAI API Key", "optional": True, "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "azure_result", "showVariableInsertButton": True}
            ]
        },
        
        "github": {
            "name": "GitHub",
            "description": "Connect to GitHub for version control and collaboration",
            "category": "Integrations",
            "inputs": [
                {"name": "input", "type": "any", "description": "Input data from previous nodes", "optional": True}
            ],
            "outputs": [
                {"name": "repositories", "type": "array", "description": "List of repositories"},
                {"name": "commits", "type": "array", "description": "List of commits"},
                {"name": "issues", "type": "array", "description": "List of issues"},
                {"name": "pull_requests", "type": "array", "description": "List of pull requests"},
                {"name": "repository_info", "type": "object", "description": "Repository information"},
                {"name": "commit_info", "type": "object", "description": "Commit information"},
                {"name": "issue_info", "type": "object", "description": "Issue information"},
                {"name": "pull_request_info", "type": "object", "description": "Pull request information"}
            ],
            "configuration": [
                {"name": "access_token", "type": "password", "description": "GitHub access token", "showVariableInsertButton": True},
                {"name": "variableName", "type": "string", "description": "Variable name for result", "default": "github_result", "showVariableInsertButton": True}
            ]
        }
    }
    
    return {
        "categories": categories,
        "nodes": node_definitions
    } 
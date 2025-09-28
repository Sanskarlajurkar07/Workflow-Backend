import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_chat_memory_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for chat_memory node type
    
    This node stores and manages chat history/memory for conversational workflows.
    """
    logger.info(f"Executing Chat Memory node {node_id}")
    
    # Extract parameters
    memory_type = node_data.get("params", {}).get("memoryType", "token_buffer")
    memory_size = node_data.get("params", {}).get("memorySize", 50)
    variable_name = node_data.get("params", {}).get("variableName", f"chat_memory_{node_id[:4]}")
    
    # Get existing memory from workflow data if it exists
    existing_memory = workflow_data.get(variable_name, {"history": [], "recent": [], "context": ""})
    
    # Get input message(s)
    input_message = inputs.get("input", None)
    
    # Process the input based on its type
    new_messages = []
    if input_message:
        if isinstance(input_message, dict):
            # Single message as a dict
            if "role" in input_message and "content" in input_message:
                new_messages.append(input_message)
            elif "message" in input_message:
                # Extract from message field
                msg = input_message["message"]
                role = input_message.get("role", "user")
                new_messages.append({"role": role, "content": msg})
        elif isinstance(input_message, list):
            # List of messages
            for msg in input_message:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    new_messages.append(msg)
                elif isinstance(msg, str):
                    new_messages.append({"role": "user", "content": msg})
        elif isinstance(input_message, str):
            # Simple string message
            new_messages.append({"role": "user", "content": input_message})
    
    # If we have new messages, add them to the history
    if new_messages:
        history = existing_memory.get("history", [])
        history.extend(new_messages)
        
        # Apply memory management based on type
        if memory_type == "token_buffer":
            # Simple approximation of tokens (words * 1.3)
            history = limit_token_buffer(history, memory_size)
        elif memory_type == "message_buffer":
            # Limit by number of messages
            history = history[-memory_size:] if len(history) > memory_size else history
        
        # Create recent messages subset (last 10 or less)
        recent = history[-10:] if len(history) > 10 else history
        
        # Create formatted context string
        context = format_chat_history(history, memory_type)
        
        # Update memory
        existing_memory = {
            "history": history,
            "recent": recent,
            "context": context
        }
        
        # Store in workflow data
        workflow_data[variable_name] = existing_memory
    
    return NodeResult(
        output=existing_memory,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Chat Memory")
    )

def limit_token_buffer(history: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
    """Limit history to approximately max_tokens by removing oldest messages first"""
    total_tokens = 0
    for i in range(len(history) - 1, -1, -1):
        # Approximate token count as words * 1.3
        message = history[i]
        content = message.get("content", "")
        if isinstance(content, str):
            words = content.split()
            message_tokens = int(len(words) * 1.3) + 5  # Add overhead for message format
            total_tokens += message_tokens
            
            if total_tokens > max_tokens and i > 0:
                # Keep current message and remove all older ones
                return history[i:]
    
    # If we get here, the total is under the limit
    return history

def format_chat_history(history: List[Dict[str, Any]], format_type: str) -> str:
    """Format chat history into a string context based on format type"""
    if format_type == "formatted_full_raw":
        # Full raw format with role prefix
        formatted = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted.append(f"{role.capitalize()}: {content}")
        return "\n\n".join(formatted)
    
    # Default format - simple concatenation with role prefix
    formatted = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content:
            prefix = "User: " if role == "user" else "Assistant: "
            formatted.append(f"{prefix}{content}")
    
    return "\n".join(formatted) 
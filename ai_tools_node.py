import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_ai_tools_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for ai_tools node type
    
    This node provides interfaces to various AI language models for generating text.
    """
    logger.info(f"Executing AI Tools node {node_id}")
    
    # Extract parameters
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "gpt-3.5-turbo")
    max_tokens = node_data.get("params", {}).get("maxTokens", 1000)
    temperature = node_data.get("params", {}).get("temperature", 0.7)
    system_prompt = node_data.get("params", {}).get("systemPrompt", "")
    prompt_template = node_data.get("params", {}).get("promptTemplate", "{{input}}")
    variable_name = node_data.get("params", {}).get("variableName", f"ai_{node_id[:4]}")
    
    # Process variables in prompt template and system prompt
    for key, value in workflow_data.items():
        var_placeholder = f"{{{{workflow.variables.{key}}}}}"
        if var_placeholder in prompt_template:
            prompt_template = prompt_template.replace(var_placeholder, str(value))
        if system_prompt and var_placeholder in system_prompt:
            system_prompt = system_prompt.replace(var_placeholder, str(value))
    
    # Get input text
    input_text = inputs.get("input", "")
    context = inputs.get("context", "")
    
    # Replace input placeholder in prompt template
    prompt = prompt_template.replace("{{input}}", str(input_text))
    if "{{context}}" in prompt and context:
        prompt = prompt.replace("{{context}}", str(context))
    
    try:
        # Create messages for API call
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add user message (the prompt)
        messages.append({"role": "user", "content": prompt})
        
        # Call the appropriate API based on provider
        api_result = await call_ai_api(provider, model, messages, max_tokens, temperature)
        
        # Process result
        result = {
            "content": api_result.get("content", ""),
            "model": model,
            "provider": provider,
            "input_tokens": api_result.get("input_tokens", 0),
            "output_tokens": api_result.get("output_tokens", 0),
            "finish_reason": api_result.get("finish_reason", "stop")
        }
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "AI Tools")
        )
    
    except Exception as e:
        logger.error(f"Error in AI Tools node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "AI Tools")
        )

async def call_ai_api(
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float
) -> Dict[str, Any]:
    """Call AI provider API and return result"""
    # This is a simplified implementation - in production code you'd use the
    # appropriate SDK for each provider
    
    # For this implementation, simulate responses
    content = f"This is a simulated response from {provider} using {model}.\n\n"
    content += "The system would use the appropriate API client in production code.\n"
    content += f"Model: {model}\n"
    content += f"Temperature: {temperature}\n"
    content += f"Max tokens: {max_tokens}\n\n"
    content += "Sample response content based on the input."
    
    if provider == "openai":
        api_result = {
            "content": content,
            "input_tokens": 50,
            "output_tokens": 70,
            "finish_reason": "stop"
        }
    elif provider == "anthropic":
        api_result = {
            "content": content,
            "input_tokens": 55,
            "output_tokens": 75,
            "finish_reason": "stop_sequence"
        }
    elif provider == "gemini":
        api_result = {
            "content": content,
            "input_tokens": 45,
            "output_tokens": 65,
            "finish_reason": "stop"
        }
    elif provider == "cohere":
        api_result = {
            "content": content,
            "input_tokens": 52,
            "output_tokens": 68,
            "finish_reason": "complete"
        }
    else:
        api_result = {
            "content": f"Unknown provider: {provider}. Please use openai, anthropic, gemini, or cohere.",
            "input_tokens": 10,
            "output_tokens": 15,
            "finish_reason": "error"
        }
    
    return api_result 
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_ai_task_executor_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for ai_task_executor node type
    
    This node performs specific AI tasks such as summarization, sentiment analysis, etc.
    """
    logger.info(f"Executing AI Task Executor node {node_id}")
    
    # Extract parameters
    task_type = node_data.get("params", {}).get("taskType", "text_summarization")
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "gpt-3.5-turbo")
    task_config = node_data.get("params", {}).get("taskConfig", {})
    variable_name = node_data.get("params", {}).get("variableName", f"task_{node_id[:4]}")
    
    # Process variables in task configuration
    if isinstance(task_config, dict):
        for config_key, config_value in list(task_config.items()):
            if isinstance(config_value, str):
                for var_key, var_value in workflow_data.items():
                    if isinstance(var_value, (str, int, float, bool)):
                        var_placeholder = f"{{{{workflow.variables.{var_key}}}}}"
                        if var_placeholder in config_value:
                            task_config[config_key] = config_value.replace(var_placeholder, str(var_value))
    
    # Get input data
    input_data = inputs.get("input", "")
    
    try:
        result = {}
        system_message = ""
        user_message = ""
        
        # Configure task based on task type
        if task_type == "text_summarization":
            system_message = "Summarize the following text concisely."
            user_message = f"Please summarize this text:\n\n{input_data}"
            
            if task_config.get("length"):
                user_message += f"\n\nSummary length: {task_config.get('length')}"
            if task_config.get("style"):
                user_message += f"\n\nStyle: {task_config.get('style')}"
        
        elif task_type == "sentiment_analysis":
            system_message = "Analyze the sentiment of the following text."
            user_message = f"Please analyze the sentiment of this text:\n\n{input_data}"
            
        elif task_type == "content_generation":
            system_message = task_config.get("instructions", "Generate content based on the instructions.")
            user_message = f"Generate content based on this input:\n\n{input_data}"
            
            if task_config.get("format"):
                user_message += f"\n\nFormat: {task_config.get('format')}"
            if task_config.get("tone"):
                user_message += f"\n\nTone: {task_config.get('tone')}"
                
        elif task_type == "translation":
            target_language = task_config.get("targetLanguage", "English")
            system_message = f"Translate the following text to {target_language}."
            user_message = f"Please translate this text to {target_language}:\n\n{input_data}"
            
        elif task_type == "text_classification":
            categories = task_config.get("categories", [])
            categories_str = ", ".join(categories) if categories else "appropriate categories"
            system_message = f"Classify the following text into {categories_str}."
            user_message = f"Please classify this text:\n\n{input_data}"
        
        # Construct messages for AI API
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # Call AI API 
        api_result = await call_ai_api(provider, model, messages, 1000, 0.7)
        
        # Process result based on task type
        if task_type == "sentiment_analysis":
            # Try to parse sentiment from response
            sentiment = "neutral"
            score = 0.0
            content = api_result.get("content", "").lower()
            
            if "positive" in content:
                sentiment = "positive"
                score = 0.8
            elif "negative" in content:
                sentiment = "negative"
                score = -0.8
            
            result = {
                "sentiment": sentiment,
                "score": score,
                "analysis": api_result.get("content")
            }
        else:
            # For other task types, return content directly
            result = {
                "result": api_result.get("content", ""),
                "task_type": task_type
            }
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "AI Task Executor")
        )
    except Exception as e:
        logger.error(f"Error in AI Task Executor node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "AI Task Executor")
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
    return {
        "content": f"This is a simulated response from {provider} using {model}.",
        "input_tokens": 50,
        "output_tokens": 20
    } 
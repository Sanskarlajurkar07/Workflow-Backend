import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
import httpx
import json
import os

# Import handlers from dedicated files
from ai_tools_node import handle_ai_tools_node
from spark_layer_node import handle_spark_layer_node
from ai_task_executor_node import handle_ai_task_executor_node

logger = logging.getLogger("workflow_api")

# AI provider API keys - should be moved to environment variables
AI_PROVIDERS = {
    "openai": {"api_key": os.environ.get("OPENAI_API_KEY", "")},
    "anthropic": {"api_key": os.environ.get("ANTHROPIC_API_KEY", "")},
    "gemini": {"api_key": os.environ.get("GOOGLE_API_KEY", "")},
    "cohere": {"api_key": os.environ.get("COHERE_API_KEY", "")}
}

async def handle_ai_tools_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for ai_tools node type"""
    logger.info(f"Executing AI Tools node {node_id}")
    
    # Extract parameters
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "gpt-3.5-turbo")
    max_tokens = node_data.get("params", {}).get("maxTokens", 1000)
    temperature = node_data.get("params", {}).get("temperature", 0.7)
    system_prompt = node_data.get("params", {}).get("systemPrompt", "")
    prompt_template = node_data.get("params", {}).get("promptTemplate", "")
    
    # Get input message and context
    input_message = inputs.get("input", "")
    context = inputs.get("context", "")
    
    # Process variables in template
    processed_prompt = prompt_template
    if "{{input}}" in processed_prompt:
        processed_prompt = processed_prompt.replace("{{input}}", str(input_message))
    if "{{context}}" in processed_prompt:
        processed_prompt = processed_prompt.replace("{{context}}", str(context))
    
    # For variable references like {{workflow.variables.x}}
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if var_placeholder in processed_prompt:
                processed_prompt = processed_prompt.replace(var_placeholder, str(value))
    
    # Construct messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Add user message with processed prompt
    messages.append({"role": "user", "content": processed_prompt})
    
    # Call AI API based on provider
    try:
        result = await call_ai_api(provider, model, messages, max_tokens, temperature)
        
        # Store result in workflow data for variable access
        var_name = node_data.get("params", {}).get("variableName", f"ai_result_{node_id[:4]}")
        workflow_data[var_name] = result.get("content", "")
        
        return NodeResult(
            output={
                "content": result.get("content", ""),
                "model": model,
                "provider": provider,
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0)
            },
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

async def handle_spark_layer_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for spark_layer node type"""
    logger.info(f"Executing SparkLayer node {node_id}")
    
    # Extract parameters
    mode = node_data.get("params", {}).get("mode", "text_to_embedding")
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "text-embedding-3-large")
    input_format = node_data.get("params", {}).get("inputFormat", "single")
    dimension = node_data.get("params", {}).get("dimension", 1536)
    
    # Get input data
    input_data = inputs.get("input", "")
    
    try:
        result = {}
        if mode == "text_to_embedding":
            # Convert text to embedding vector
            if input_format == "batch" and isinstance(input_data, list):
                # Process batch of text
                embeddings = []
                for text in input_data:
                    # Simulate embedding generation for now
                    # In production, call actual embedding API
                    embedding = [0.01] * min(10, dimension)  # Mock embedding
                    embeddings.append(embedding)
                result = {"embeddings": embeddings, "count": len(embeddings)}
            else:
                # Process single text
                # Simulate embedding generation
                embedding = [0.01] * min(10, dimension)  # Mock embedding
                result = {"embedding": embedding, "dimension": len(embedding)}
        
        elif mode == "embedding_similarity":
            # Calculate similarity between embeddings
            # For demo, return mock similarity scores
            result = {"similarity": 0.85, "method": "cosine"}
        
        elif mode == "semantic_search":
            # Perform semantic search
            # For demo, return mock search results
            result = {
                "results": [
                    {"score": 0.95, "content": "Example result 1", "id": "1"},
                    {"score": 0.82, "content": "Example result 2", "id": "2"}
                ]
            }
        
        # Store result in workflow data for variable access
        var_name = node_data.get("params", {}).get("variableName", f"embedding_{node_id[:4]}")
        workflow_data[var_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
        )
    except Exception as e:
        logger.error(f"Error in SparkLayer node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
        )

async def handle_ai_task_executor_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for ai_task_executor node type"""
    logger.info(f"Executing AI Task Executor node {node_id}")
    
    # Extract parameters
    task_type = node_data.get("params", {}).get("taskType", "text_summarization")
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "gpt-3.5-turbo")
    task_config = node_data.get("params", {}).get("taskConfig", {})
    
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
        var_name = node_data.get("params", {}).get("variableName", f"task_{node_id[:4]}")
        workflow_data[var_name] = result
        
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
    
    # Check if simulation mode is enabled
    simulate = os.getenv("SIMULATE", "false").lower() == "true"
    if simulate:
        logger.info(f"SIMULATE mode enabled - returning mock response for {provider}")
        return {
            "content": f"[SIMULATED] This is a simulated response from {provider} using {model}.",
            "input_tokens": 50,
            "output_tokens": 20
        }
    
    logger.info(f"Making real API call to {provider} with model {model}")
    
    try:
        if provider.lower() == "openai":
            return await call_openai_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "anthropic":
            return await call_anthropic_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "gemini":
            return await call_gemini_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "cohere":
            return await call_cohere_api(model, messages, max_tokens, temperature)
        else:
            logger.error(f"Unsupported AI provider: {provider}")
            return {
                "content": f"Error: Unsupported AI provider: {provider}",
                "input_tokens": 0,
                "output_tokens": 0,
                "error": "unsupported_provider"
            }
    except Exception as e:
        logger.error(f"Error calling {provider} API: {str(e)}", exc_info=True)
        return {
            "content": f"Error calling {provider} API: {str(e)}",
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e)
        }

async def call_openai_api(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call OpenAI API"""
    try:
        import openai
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return {
            "content": response.choices[0].message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens
        }
    except ImportError:
        raise Exception("OpenAI package not installed. Run: pip install openai")
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

async def call_anthropic_api(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call Anthropic Claude API"""
    try:
        import anthropic
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Format messages for Anthropic API
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        response = client.messages.create(
            model=model,
            system=system_message,
            messages=formatted_messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return {
            "content": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    except ImportError:
        raise Exception("Anthropic package not installed. Run: pip install anthropic")
    except Exception as e:
        raise Exception(f"Anthropic API error: {str(e)}")

async def call_gemini_api(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call Google Gemini API"""
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        
        # Initialize model
        gemini_model = genai.GenerativeModel(model)
        
        # Format messages for Gemini API (it expects a different format)
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "model", "parts": [msg["content"]]})
            # Skip system messages for now as Gemini handles them differently
        
        # Get the last user message for generation
        user_content = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_content = msg["content"]
                break
        
        # Generate response
        response = gemini_model.generate_content(
            user_content,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        )
        
        return {
            "content": response.text,
            "input_tokens": 0,  # Gemini doesn't provide token counts
            "output_tokens": 0
        }
    except ImportError:
        raise Exception("Google Generative AI package not installed. Run: pip install google-generativeai")
    except Exception as e:
        raise Exception(f"Gemini API error: {str(e)}")

async def call_cohere_api(model: str, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call Cohere API"""
    try:
        import cohere
        
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY not found in environment variables")
        
        client = cohere.Client(api_key)
        
        # Get the prompt from the last user message
        prompt = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                prompt = msg["content"]
                break
        
        response = client.generate(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return {
            "content": response.generations[0].text,
            "input_tokens": response.meta.billed_units.input_tokens if hasattr(response, "meta") and hasattr(response.meta, "billed_units") else 0,
            "output_tokens": response.meta.billed_units.output_tokens if hasattr(response, "meta") and hasattr(response.meta, "billed_units") else 0
        }
    except ImportError:
        raise Exception("Cohere package not installed. Run: pip install cohere")
    except Exception as e:
        raise Exception(f"Cohere API error: {str(e)}")

# Export the imported handlers directly
__all__ = [
    "handle_ai_tools_node",
    "handle_spark_layer_node",
    "handle_ai_task_executor_node"
] 
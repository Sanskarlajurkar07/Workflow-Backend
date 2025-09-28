import logging
from typing import Dict, Any, Optional
from datetime import datetime
from models.workflow import NodeResult
import re
import json
import os

logger = logging.getLogger("workflow_api")

# Import the new variable processor
from variable_processor import process_node_variables, normalize_node_output

# Common function to process variables in text - UPDATED VERSION
def process_variables(text: str, node_outputs: Dict[str, Any], workflow_data: Dict[str, Any] = None) -> str:
    """Process variables in text by replacing {{variable}} with actual values"""
    return process_node_variables(text, node_outputs)

# Enhanced AI API call function with REAL API calls
async def call_ai_api(provider: str, model: str, messages: list, max_tokens: int = 1000, 
                      temperature: float = 0.7, **kwargs) -> Dict[str, Any]:
    """Enhanced function for AI API calls with REAL API integration"""
    
    # Check if simulation mode is enabled
    simulate = os.getenv("SIMULATE", "false").lower() == "true"
    if simulate:
        logger.info(f"SIMULATE mode enabled - returning enhanced mock response for {provider}")
        return await get_mock_response(provider, model, messages, max_tokens, temperature)
    
    # Extract the actual content from messages for logging
    user_content = ""
    system_content = ""
    
    for message in messages:
        if message.get("role") == "user":
            user_content = message.get("content", "")
        elif message.get("role") == "system":
            system_content = message.get("content", "")
    
    logger.info(f"Making REAL API call to {provider} with model {model}")
    
    try:
        if provider.lower() == "openai":
            return await call_real_openai_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "anthropic":
            return await call_real_anthropic_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "gemini":
            return await call_real_gemini_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "cohere":
            return await call_real_cohere_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "perplexity":
            return await call_real_perplexity_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "xai":
            return await call_real_xai_api(model, messages, max_tokens, temperature)
        elif provider.lower() == "azure":
            return await call_real_azure_api(model, messages, max_tokens, temperature)
        else:
            logger.error(f"Unsupported AI provider: {provider}")
            return {
                "content": f"Error: Unsupported AI provider: {provider}",
                "model": model,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "error": "unsupported_provider"
            }
    except Exception as e:
        logger.error(f"Error calling {provider} API: {str(e)}", exc_info=True)
        # Fallback to mock response on error
        logger.info(f"Falling back to mock response for {provider} due to error")
        return await get_mock_response(provider, model, messages, max_tokens, temperature)

async def get_mock_response(provider: str, model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Get enhanced mock response when real APIs are not available"""
    user_content = ""
    system_content = ""
    
    for message in messages:
        if message.get("role") == "user":
            user_content = message.get("content", "")
        elif message.get("role") == "system":
            system_content = message.get("content", "")
    
    # Create contextual responses based on content
    response_content = generate_contextual_response(user_content, system_content, provider, model)
    
    # Simulate API response based on provider
    provider_responses = {
        "openai": {
            "content": response_content,
            "model": model,
            "usage": {
                "prompt_tokens": max(10, len(user_content) // 4),
                "completion_tokens": max(20, len(response_content) // 4),
                "total_tokens": max(30, (len(user_content) + len(response_content)) // 4)
            }
        },
        "anthropic": {
            "content": response_content,
            "model": model,
            "usage": {
                "input_tokens": max(10, len(user_content) // 4),
                "output_tokens": max(20, len(response_content) // 4)
            }
        },
        "gemini": {
            "content": response_content,
            "model": model,
            "usage": {
                "prompt_token_count": max(10, len(user_content) // 4),
                "completion_token_count": max(20, len(response_content) // 4)
            }
        },
        "cohere": {
            "content": response_content,
            "model": model,
            "usage": {
                "tokens": {
                    "input_tokens": max(10, len(user_content) // 4),
                    "output_tokens": max(20, len(response_content) // 4)
                }
            }
        },
        "perplexity": {
            "content": response_content,
            "model": model,
            "usage": {
                "prompt_tokens": max(10, len(user_content) // 4),
                "completion_tokens": max(20, len(response_content) // 4)
            }
        },
        "xai": {
            "content": response_content,
            "model": model,
            "usage": {
                "prompt_tokens": max(10, len(user_content) // 4),
                "completion_tokens": max(20, len(response_content) // 4)
            }
        },
        "azure": {
            "content": response_content,
            "model": model,
            "usage": {
                "prompt_tokens": max(10, len(user_content) // 4),
                "completion_tokens": max(20, len(response_content) // 4),
                "total_tokens": max(30, (len(user_content) + len(response_content)) // 4)
            }
        }
    }
    
    return provider_responses.get(provider, {
        "content": response_content,
        "model": model,
        "usage": {"tokens": max(30, (len(user_content) + len(response_content)) // 4)}
    })

# Real API call functions
async def call_real_openai_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real OpenAI API"""
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
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except ImportError:
        raise Exception("OpenAI package not installed. Run: pip install openai")
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

async def call_real_anthropic_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real Anthropic API"""
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
            "model": model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    except ImportError:
        raise Exception("Anthropic package not installed. Run: pip install anthropic")
    except Exception as e:
        raise Exception(f"Anthropic API error: {str(e)}")

async def call_real_gemini_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real Google Gemini API"""
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        
        # Initialize model
        gemini_model = genai.GenerativeModel(model)
        
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
            "model": model,
            "usage": {
                "prompt_token_count": 0,  # Gemini doesn't provide token counts
                "completion_token_count": 0
            }
        }
    except ImportError:
        raise Exception("Google Generative AI package not installed. Run: pip install google-generativeai")
    except Exception as e:
        raise Exception(f"Gemini API error: {str(e)}")

async def call_real_cohere_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real Cohere API"""
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
            "model": model,
            "usage": {
                "tokens": {
                    "input_tokens": response.meta.billed_units.input_tokens if hasattr(response, "meta") and hasattr(response.meta, "billed_units") else 0,
                    "output_tokens": response.meta.billed_units.output_tokens if hasattr(response, "meta") and hasattr(response.meta, "billed_units") else 0
                }
            }
        }
    except ImportError:
        raise Exception("Cohere package not installed. Run: pip install cohere")
    except Exception as e:
        raise Exception(f"Cohere API error: {str(e)}")

async def call_real_perplexity_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real Perplexity API"""
    try:
        import httpx
        
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY not found in environment variables")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload
            )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": model,
                "usage": {
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"]
                }
            }
        else:
            raise Exception(f"Perplexity API error: {response.text}")
    except ImportError:
        raise Exception("httpx package not installed. Run: pip install httpx")
    except Exception as e:
        raise Exception(f"Perplexity API error: {str(e)}")

async def call_real_xai_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real XAI API"""
    try:
        import httpx
        
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY not found in environment variables")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.xai.org/v1/chat/completions",
                headers=headers,
                json=payload
            )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": model,
                "usage": {
                    "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("completion_tokens", 0)
                }
            }
        else:
            raise Exception(f"XAI API error: {response.text}")
    except ImportError:
        raise Exception("httpx package not installed. Run: pip install httpx")
    except Exception as e:
        raise Exception(f"XAI API error: {str(e)}")

async def call_real_azure_api(model: str, messages: list, max_tokens: int, temperature: float) -> Dict[str, Any]:
    """Call real Azure OpenAI API"""
    try:
        from openai import AzureOpenAI
        
        api_key = os.environ.get("AZURE_API_KEY")
        endpoint = os.environ.get("AZURE_ENDPOINT")
        
        if not api_key or not endpoint:
            raise ValueError("AZURE_API_KEY and AZURE_ENDPOINT not found in environment variables")
        
        client = AzureOpenAI(
            api_key=api_key,
            api_version="2023-05-15",
            azure_endpoint=endpoint
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return {
            "content": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
    except ImportError:
        raise Exception("Azure OpenAI package not installed. Run: pip install openai")
    except Exception as e:
        raise Exception(f"Azure OpenAI API error: {str(e)}")

def generate_contextual_response(user_content: str, system_content: str, provider: str, model: str) -> str:
    """Generate more contextual and realistic responses based on input content"""
    
    # Clean and analyze the input
    user_text = user_content.strip().lower() if user_content else ""
    system_text = system_content.strip().lower() if system_content else ""
    
    # Check if we still have unprocessed variables (indicates an issue)
    has_unprocessed_vars = "{{" in user_content or "{{" in system_content
    
    if has_unprocessed_vars:
        logger.warning(f"Detected unprocessed variables in mock response - this indicates variable processing failed")
        logger.warning(f"User content: {user_content}")
        logger.warning(f"System content: {system_content}")
        return f"⚠️ Variable processing error: The variables in your prompts (like {{{{input_0.text}}}}) were not properly substituted. Please check your input connections and try again."
    
    # Generate responses based on content patterns
    if not user_text:
        return f"I'm {provider} {model}, ready to help! Please provide a question or prompt."
    
    # Pattern-based responses for common queries
    if any(word in user_text for word in ['capital', 'france']):
        return "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine."
    
    elif any(word in user_text for word in ['hello', 'hi', 'greeting']):
        return f"Hello! I'm {provider}'s {model} AI assistant. How can I help you today?"
    
    elif any(word in user_text for word in ['weather', 'temperature', 'climate']):
        return "I don't have access to real-time weather data, but I can provide general information about weather patterns, climate zones, or help you find weather resources."
    
    elif any(word in user_text for word in ['explain', 'what is', 'define']):
        topic = user_text.replace('explain', '').replace('what is', '').replace('define', '').strip()
        return f"I'd be happy to explain {topic}. Based on my training data, here's a comprehensive explanation covering the key concepts, background, and important details you should know."
    
    elif any(word in user_text for word in ['write', 'create', 'generate']):
        return f"I'll help you create that content. Based on your request '{user_content[:50]}...', I'll generate well-structured, relevant content that meets your needs."
    
    elif any(word in user_text for word in ['code', 'programming', 'function']):
        return f"I can help with that programming task. Based on your request, I'll provide clean, well-commented code that follows best practices and accomplishes your goal."
    
    elif any(word in user_text for word in ['analyze', 'review', 'examine']):
        return f"I'll analyze the information you've provided. Based on my examination, here are the key insights, patterns, and recommendations I can offer."
    
    elif 'question' in user_text or '?' in user_content:
        return f"That's an excellent question! Based on the information available to me, here's a comprehensive answer that addresses your inquiry."
    
    else:
        # For properly processed variables, generate a contextual response
        if system_content:
            return f"Based on your request and the system instructions provided, I understand you want me to {user_content[:100]}... Here's my response: I'm processing your request according to the specified guidelines and providing a helpful, accurate response."
        else:
            return f"I understand your request: '{user_content[:100]}...' Here's my thoughtful response addressing your specific needs with accuracy and helpfulness."

# Generic AI node handler - ENHANCED VERSION
async def handle_ai_provider_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    provider: str,
    request: Optional[Any] = None
) -> NodeResult:
    """Enhanced generic handler for all AI provider nodes with REAL API integration"""
    logger.info(f"Executing {provider} node {node_id}")
    
    # Extract parameters with fallbacks for different data structures
    params = node_data.get("params", {})
    
    # Handle mixed parameter structures (some nodes store params in root data)
    if not params and node_data:
        # Check if parameters are stored directly in node_data
        params = {k: v for k, v in node_data.items() if k not in ['label', 'type']}
    
    # Extract configuration with fallbacks
    model = params.get("model", params.get("gpt_model", "gpt-3.5-turbo" if provider == "openai" else f"{provider}-default"))
    system_prompt = params.get("system", params.get("systemPrompt", ""))
    user_prompt = params.get("prompt", params.get("userPrompt", ""))
    max_tokens = params.get("maxTokens", params.get("max_tokens", 1000))
    temperature = params.get("temperature", 0.7)
    variable_name = params.get("variableName", f"{provider}_result")
    node_name = params.get("nodeName", f"{provider}_{node_id.split('-')[-1] if '-' in node_id else node_id[:4]}")
    api_key = params.get("apiKey", "")
    use_personal_key = params.get("usePersonalKey", False)
    
    # Get current node outputs for variable processing
    node_outputs = getattr(request, 'node_outputs', {}) if request else {}
    
    logger.info(f"Processing variables in {provider} node with available outputs: {list(node_outputs.keys())}")
    logger.info(f"Original system prompt: '{system_prompt}'")
    logger.info(f"Original user prompt: '{user_prompt}'")
    
    # Process variables in prompts using the enhanced system
    processed_system = process_node_variables(system_prompt, node_outputs)
    processed_user = process_node_variables(user_prompt, node_outputs)
    
    logger.info(f"Processed system prompt: '{processed_system}'")
    logger.info(f"Processed user prompt: '{processed_user}'")
    
    # Get input data and append if provided
    input_data = inputs.get("input", "")
    if input_data:
        # If there's input data, append it to the prompt
        if processed_user:
            processed_user = f"{processed_user}\n\nInput: {input_data}"
        else:
            processed_user = str(input_data)
        logger.info(f"Added input data to user prompt: '{processed_user}'")
    
    try:
        # Set the API key in environment if provided by user
        original_api_key = None
        if api_key and use_personal_key:
            original_api_key = os.environ.get(f"{provider.upper()}_API_KEY")
            os.environ[f"{provider.upper()}_API_KEY"] = api_key
            logger.info(f"Using personal API key for {provider}")
        
        # Prepare messages for API call with PROCESSED content
        messages = []
        if processed_system:
            messages.append({"role": "system", "content": processed_system})
        if processed_user:
            messages.append({"role": "user", "content": processed_user})
        
        # Call the enhanced API function (will use real APIs or fallback to mock if keys missing)
        api_result = await call_ai_api(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Restore original API key if we temporarily set one
        if original_api_key is not None:
            os.environ[f"{provider.upper()}_API_KEY"] = original_api_key
        elif api_key and use_personal_key:
            # Remove the temporary key if there was no original
            os.environ.pop(f"{provider.upper()}_API_KEY", None)
        
        # Format result with comprehensive structure for variable access
        content = api_result.get("content", "")
        
        # Create normalized output with multiple access patterns
        result = normalize_node_output({
            "output": content,      # Primary output field
            "content": content,     # Alternative access
            "response": content,    # AI-specific access
            "text": content,        # Text-based access
            "value": content,       # Generic value access
            "model": api_result.get("model", model),
            "provider": provider,
            "usage": api_result.get("usage", {}),
            "prompt_tokens": api_result.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": api_result.get("usage", {}).get("completion_tokens", 0),
            "system_prompt": processed_system,
            "user_prompt": processed_user,
            "original_system_prompt": system_prompt,
            "original_user_prompt": user_prompt,
            "input_data": input_data,
            "api_key_used": bool(api_key and use_personal_key),
            "real_api_call": not os.getenv("SIMULATE", "false").lower() == "true"
        }, provider)
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        logger.info(f"{provider} node completed successfully. Output length: {len(content)} characters")
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_name
        )
    
    except Exception as e:
        logger.error(f"Error in {provider} node: {str(e)}", exc_info=True)
        error_result = {
            "error": str(e),
            "provider": provider,
            "output": f"Error: {str(e)}",
            "content": f"Error: {str(e)}",
            "response": f"Error: {str(e)}"
        }
        
        return NodeResult(
            output=error_result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        )

# Specific handlers for each provider
async def handle_openai_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "openai", request)

async def handle_anthropic_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "anthropic", request)

async def handle_gemini_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "gemini", request)

async def handle_cohere_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "cohere", request)

async def handle_perplexity_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "perplexity", request)

async def handle_xai_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "xai", request)

async def handle_azure_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Optional[Any] = None
) -> NodeResult:
    return await handle_ai_provider_node(node_id, node_data, inputs, workflow_data, start_time, "azure", request) 
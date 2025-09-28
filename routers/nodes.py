from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from models.user import User
from routers.auth import get_current_user_optional_token
from typing import Dict, Any, Optional
import logging
import os
import time
from models.integrations import IntegrationType

# Initialize router
router = APIRouter()
logger = logging.getLogger("workflow_api")

# API key configurations (should be moved to a secure storage in production)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # For Gemini
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY", "")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY", "")
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "")
AZURE_ENDPOINT = os.environ.get("AZURE_ENDPOINT", "")

# Routes for model management
@router.get("/models", response_model=Dict[str, Any])
async def list_models(
    request: Request, 
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get a list of available AI models for each provider"""
    return {
        "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"],
        "anthropic": ["claude-3-haiku", "claude-3-sonnet", "claude-3-opus"],
        "gemini": ["gemini-pro", "gemini-pro-vision", "gemini-flash"],
        "cohere": ["command", "command-light", "command-plus", "command-r"],
        "perplexity": ["sonar-small", "sonar-medium", "sonar-large"],
        "xai": ["xai-chat"],
        "aws": ["amazon-titan", "claude-3-sonnet", "claude-3-haiku"],
        "azure": ["gpt-35-turbo", "gpt-4", "gpt-4-turbo"]
    }

@router.post("/query/{provider}", response_model=Dict[str, Any])
async def query_model(
    provider: str,
    request_data: Dict[str, Any],
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Query an AI model from the specified provider"""
    start_time = time.time()
    provider = provider.lower()
    
    logger.info(f"Processing {provider} model query: {request_data.get('model', 'unknown')}")
    
    try:
        # Check provider and call appropriate handler
        if provider == "openai":
            response = await handle_openai_query(request_data)
        elif provider == "anthropic":
            response = await handle_anthropic_query(request_data)
        elif provider == "gemini":
            response = await handle_gemini_query(request_data)
        elif provider == "cohere":
            response = await handle_cohere_query(request_data)
        elif provider == "perplexity":
            response = await handle_perplexity_query(request_data)
        elif provider == "xai":
            response = await handle_xai_query(request_data)
        elif provider == "aws":
            response = await handle_aws_query(request_data)
        elif provider == "azure":
            response = await handle_azure_query(request_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
        
        processing_time = time.time() - start_time
        
        # Log usage for billing/monitoring (in a real production app)
        background_tasks.add_task(
            log_model_usage,
            user_id=str(current_user.id),
            provider=provider,
            model=request_data.get("model", "unknown"),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
            processing_time=processing_time
        )
        
        return {
            "response": response.get("content", ""),
            "model": request_data.get("model", "unknown"),
            "provider": provider,
            "processing_time": processing_time,
            "input_tokens": response.get("input_tokens", 0),
            "output_tokens": response.get("output_tokens", 0)
        }
        
    except Exception as e:
        logger.error(f"Error processing {provider} query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing {provider} query: {str(e)}"
        )

# Model handlers
async def handle_openai_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle OpenAI model requests"""
    try:
        # Check if OpenAI package is installed
        import openai
        
        # Get the API key from the request if provided by the user, otherwise use system key
        user_api_key = data.get("apiKey")
        system_api_key = OPENAI_API_KEY
        
        # Use user API key if provided, otherwise fall back to system key
        api_key = user_api_key if user_api_key else system_api_key
        
        # If no API key is available, return a clear error
        if not api_key:
            logger.warning("No OpenAI API key available. Please set OPENAI_API_KEY in environment variables.")
            return {
                "content": "⚠️ No OpenAI API key configured. Please contact the administrator.",
                "input_tokens": 0,
                "output_tokens": 0,
                "error": "missing_api_key"
            }
        
        # Configure client
        client = openai.OpenAI(api_key=api_key)
        
        # Extract parameters
        model = data.get("model", "gpt-3.5-turbo")
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        
        # Call API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Format response
        return {
            "content": response.choices[0].message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens
        }
        
    except ImportError:
        # If OpenAI package is not installed, provide a clear deployment error
        logger.error("OpenAI package not installed. Install with 'pip install openai'")
        return {
            "content": "⚠️ OpenAI integration not installed on the server. Please contact the administrator.",
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "missing_dependency"
        }
    except Exception as e:
        # Log the specific error for debugging
        logger.error(f"OpenAI API error: {str(e)}")
        return {
            "content": f"⚠️ Error calling OpenAI API: {str(e)}",
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "api_error"
        }

async def handle_anthropic_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Anthropic Claude model requests"""
    try:
        # Check if Anthropic package is installed
        import anthropic
        
        # Configure client
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Extract parameters
        model = data.get("model", "claude-3-sonnet")
        system = data.get("system", "")
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens", 1000)
        
        # Format messages for Anthropic API
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "assistant", "content": msg["content"]})
        
        # Call API
        response = client.messages.create(
            model=model,
            system=system,
            messages=formatted_messages,
            max_tokens=max_tokens
        )
        
        # Format response
        return {
            "content": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
        
    except ImportError:
        # If Anthropic package is not installed, simulate response for testing
        return simulate_ai_response("anthropic")

async def handle_gemini_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Google Gemini model requests"""
    try:
        # Check if Google Generative AI package is installed
        import google.generativeai as genai
        
        # Configure client
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Extract parameters
        model = data.get("model", "gemini-pro")
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.7)
        
        # Format messages for Gemini API
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                formatted_messages.append({"role": "model", "parts": [msg["content"]]})
        
        # Initialize model
        gemini_model = genai.GenerativeModel(model)
        
        # Create chat session
        chat = gemini_model.start_chat(history=formatted_messages)
        
        # Generate response
        response = chat.send_message(
            formatted_messages[-1]["parts"][0] if formatted_messages else "",
            generation_config={"temperature": temperature}
        )
        
        # Format response (Gemini doesn't provide token counts)
        return {
            "content": response.text,
            "input_tokens": 0,  # Not provided by Gemini
            "output_tokens": 0  # Not provided by Gemini
        }
        
    except ImportError:
        # If Google package is not installed, simulate response for testing
        return simulate_ai_response("gemini")

async def handle_cohere_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Cohere model requests"""
    try:
        # Check if Cohere package is installed
        import cohere
        
        # Configure client
        client = cohere.Client(COHERE_API_KEY)
        
        # Extract parameters
        model = data.get("model", "command")
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        
        # Get the prompt from the last user message
        prompt = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                prompt = msg["content"]
                break
        
        # Call API
        response = client.generate(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Format response
        return {
            "content": response.generations[0].text,
            "input_tokens": response.meta.billed_units.input_tokens if hasattr(response, "meta") else 0,
            "output_tokens": response.meta.billed_units.output_tokens if hasattr(response, "meta") else 0
        }
        
    except ImportError:
        # If Cohere package is not installed, simulate response for testing
        return simulate_ai_response("cohere")

async def handle_perplexity_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Perplexity model requests"""
    try:
        # For Perplexity, we'll use requests to call their API
        import requests
        
        # Extract parameters
        model = data.get("model", "sonar-medium")
        messages = data.get("messages", [])
        
        # Prepare API call
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages
        }
        
        # Call API
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "input_tokens": data["usage"]["prompt_tokens"],
                "output_tokens": data["usage"]["completion_tokens"]
            }
        else:
            raise Exception(f"Perplexity API error: {response.text}")
        
    except ImportError:
        # If requests package is not installed, simulate response for testing
        return simulate_ai_response("perplexity")

async def handle_xai_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle XAI model requests"""
    try:
        # For XAI, we'll use requests to call their API
        import requests
        
        # Extract parameters
        messages = data.get("messages", [])
        
        # Prepare API call
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": messages
        }
        
        # Call API (example endpoint, might need adjustment)
        response = requests.post(
            "https://api.xai.org/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "output_tokens": data.get("usage", {}).get("completion_tokens", 0)
            }
        else:
            raise Exception(f"XAI API error: {response.text}")
        
    except ImportError:
        # If requests package is not installed, simulate response for testing
        return simulate_ai_response("xai")

async def handle_aws_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle AWS Bedrock model requests"""
    try:
        # Check if Boto3 is installed
        import boto3
        import json
        
        # Extract parameters
        model = data.get("model", "amazon-titan")
        messages = data.get("messages", [])
        
        # Configure client
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name="us-east-1",  # change as needed
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY
        )
        
        # Format messages based on model
        if "claude" in model:
            # Format for Anthropic models in Bedrock
            prompt = "\n\nHuman: "
            for msg in messages:
                if msg["role"] == "user":
                    prompt += msg["content"] + "\n\nHuman: "
                elif msg["role"] == "assistant":
                    prompt += msg["content"] + "\n\nAssistant: "
            
            # Remove the last Human: or Assistant:
            prompt = prompt.rstrip("\n\nHuman: ").rstrip("\n\nAssistant: ")
            prompt += "\n\nAssistant: "
            
            request_body = {
                "prompt": prompt,
                "max_tokens_to_sample": 500,
                "temperature": 0.7,
                "anthropic_version": "bedrock-2023-05-31"
            }
        else:
            # Format for Amazon Titan models
            request_body = {
                "inputText": messages[-1]["content"] if messages else "",
                "textGenerationConfig": {
                    "maxTokenCount": 500,
                    "temperature": 0.7,
                    "topP": 0.9
                }
            }
        
        # Call API
        response = bedrock_runtime.invoke_model(
            modelId=model,
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response["body"].read())
        
        # Extract response based on model
        if "claude" in model:
            content = response_body.get("completion", "")
        else:
            content = response_body.get("results", [{"outputText": ""}])[0]["outputText"]
        
        # Format response
        return {
            "content": content,
            "input_tokens": 0,  # AWS doesn't provide token counts in the same way
            "output_tokens": 0
        }
        
    except ImportError:
        # If Boto3 package is not installed, simulate response for testing
        return simulate_ai_response("aws")

async def handle_azure_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Azure OpenAI model requests"""
    try:
        # Check if Azure OpenAI package is installed
        from openai import AzureOpenAI
        
        # Configure client
        client = AzureOpenAI(
            api_key=AZURE_API_KEY,
            api_version="2023-05-15",  # Update as needed
            azure_endpoint=AZURE_ENDPOINT
        )
        
        # Extract parameters
        model = data.get("model", "gpt-35-turbo")
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        
        # Call API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Format response
        return {
            "content": response.choices[0].message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens
        }
        
    except ImportError:
        # If Azure OpenAI package is not installed, simulate response for testing
        return simulate_ai_response("azure")

# Helper function for testing when packages aren't installed
def simulate_ai_response(provider: str) -> Dict[str, Any]:
    """Simulate an AI response for testing when the required package is not installed"""
    return {
        "content": f"This is a simulated response from {provider}. The actual API package is not installed.",
        "input_tokens": 10,
        "output_tokens": 15
    }

# Logging function
async def log_model_usage(
    user_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    processing_time: float
):
    """Log model usage for billing and monitoring"""
    logger.info(
        f"AI Model Usage - User: {user_id}, Provider: {provider}, Model: {model}, "
        f"Input tokens: {input_tokens}, Output tokens: {output_tokens}, "
        f"Processing time: {processing_time:.3f}s"
    )
    
    # In a production app, you would store this in a database
    # For example:
    # await request.app.mongodb.model_usage.insert_one({
    #     "user_id": user_id,
    #     "provider": provider,
    #     "model": model,
    #     "input_tokens": input_tokens,
    #     "output_tokens": output_tokens,
    #     "processing_time": processing_time,
    #     "timestamp": datetime.utcnow()
    # }) 

# Routes for node definitions
@router.get("/definitions", response_model=Dict[str, Any])
async def get_node_definitions(
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get definitions of available workflow nodes"""
    # Import the node handler registration function
    from node_handlers import register_node_definitions
    
    # Use our node registration function
    definitions = await register_node_definitions(request)
    return definitions

@router.get("/integrations/status", response_model=Dict[str, Any])
async def check_integration_status(
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Check which integration services the user has connected"""
    if not current_user:
        return {
            "github": False,
            "airtable": False,
            "notion": False
        }
    
    try:
        # Find user's integration credentials
        github_cred = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.GITHUB
        })
        
        airtable_cred = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.AIRTABLE
        })
        
        notion_cred = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.NOTION
        })
        
        # Return connection status for each service
        return {
            "github": github_cred is not None,
            "airtable": airtable_cred is not None,
            "notion": notion_cred is not None,
            "setup_url": "/integrations"  # URL to the integrations setup page
        }
    except Exception as e:
        logger.error(f"Error checking integration status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error checking integration status: {str(e)}"
        ) 
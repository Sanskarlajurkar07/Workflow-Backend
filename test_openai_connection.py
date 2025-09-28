import asyncio
import os
from openai import AsyncOpenAI
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_openai_connection():
    try:
        # Get API key from environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("No OpenAI API key found in environment")
            return False
            
        logger.info(f"Found API key (last 4): ...{api_key[-4:]}")
        
        # Configure client with timeout
        client = AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(60.0, connect=30.0)
        )
        
        # Test message
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello!"}
        ]
        
        logger.info("Making test API call...")
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=50
        )
        
        content = response.choices[0].message.content
        logger.info(f"API call successful! Response: {content}")
        return True
        
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_openai_connection()) 
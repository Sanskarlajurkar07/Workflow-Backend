#!/usr/bin/env python3
"""
Test script to verify real AI API calls are working
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

# Import our AI handlers
from ai_node_handlers import call_ai_api as call_ai_api_simple
from ai_providers_node import call_ai_api as call_ai_api_enhanced

async def test_openai_api():
    """Test OpenAI API integration"""
    print("🔬 Testing OpenAI API...")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    messages = [
        {"role": "user", "content": "Hello! Please respond with 'API test successful' if you receive this message."}
    ]
    
    try:
        # Test with the enhanced API handler
        result = await call_ai_api_enhanced(
            provider="openai",
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=50,
            temperature=0.7
        )
        
        print(f"✅ OpenAI API Response: {result['content'][:100]}...")
        print(f"📊 Usage: {result.get('usage', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API Error: {str(e)}")
        return False

async def test_simulate_mode():
    """Test simulation mode"""
    print("\n🔬 Testing Simulation Mode...")
    
    # Temporarily set SIMULATE=true
    original_simulate = os.getenv("SIMULATE")
    os.environ["SIMULATE"] = "true"
    
    messages = [
        {"role": "user", "content": "This is a test in simulation mode"}
    ]
    
    try:
        result = await call_ai_api_enhanced(
            provider="openai",
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=50,
            temperature=0.7
        )
        
        print(f"✅ Simulation Response: {result['content'][:100]}...")
        
        # Restore original SIMULATE setting
        if original_simulate:
            os.environ["SIMULATE"] = original_simulate
        else:
            os.environ.pop("SIMULATE", None)
        
        return True
        
    except Exception as e:
        print(f"❌ Simulation Error: {str(e)}")
        return False

async def test_multiple_providers():
    """Test multiple AI providers if keys are available"""
    print("\n🔬 Testing Multiple Providers...")
    
    providers = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY", 
        "gemini": "GOOGLE_API_KEY",
        "cohere": "COHERE_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY"
    }
    
    results = {}
    
    for provider, env_key in providers.items():
        api_key = os.getenv(env_key)
        if not api_key:
            print(f"⚠️  {provider}: No API key configured")
            results[provider] = "not_configured"
            continue
        
        print(f"🔬 Testing {provider}...")
        
        messages = [
            {"role": "user", "content": f"Hello from {provider} test. Please respond briefly."}
        ]
        
        try:
            result = await call_ai_api_enhanced(
                provider=provider,
                model="gpt-3.5-turbo" if provider == "openai" else f"{provider}-default",
                messages=messages,
                max_tokens=50,
                temperature=0.7
            )
            
            print(f"✅ {provider}: {result['content'][:50]}...")
            results[provider] = "success"
            
        except Exception as e:
            print(f"❌ {provider}: {str(e)}")
            results[provider] = "error"
    
    return results

async def test_workflow_integration():
    """Test a simple workflow-like scenario"""
    print("\n🔬 Testing Workflow Integration...")
    
    try:
        # Import workflow components
        from ai_providers_node import handle_openai_node
        import time
        
        # Mock workflow data
        node_data = {
            "params": {
                "model": "gpt-3.5-turbo",
                "systemPrompt": "You are a helpful assistant.",
                "userPrompt": "What is the capital of France?",
                "maxTokens": 100,
                "temperature": 0.7,
                "variableName": "test_result"
            }
        }
        
        inputs = {}
        workflow_data = {}
        start_time = time.time()
        
        result = await handle_openai_node(
            node_id="test-node-001",
            node_data=node_data,
            inputs=inputs,
            workflow_data=workflow_data,
            start_time=start_time
        )
        
        if result.status == "success":
            print(f"✅ Workflow Integration: {result.output.get('content', '')[:100]}...")
            print(f"📊 Stored in workflow_data: {list(workflow_data.keys())}")
            return True
        else:
            print(f"❌ Workflow Integration Failed: {result.error}")
            return False
            
    except Exception as e:
        print(f"❌ Workflow Integration Error: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🚀 AI API Integration Test Suite")
    print("=" * 50)
    
    # Check environment setup
    print("🔍 Checking Environment Setup...")
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"✅ .env file found: {env_file}")
    else:
        print(f"⚠️  .env file not found: {env_file}")
        print("💡 Run 'python setup_env.py' to create one")
    
    # Check simulation mode
    simulate = os.getenv("SIMULATE", "false").lower() == "true"
    if simulate:
        print("🔄 SIMULATE mode is ENABLED - will use mock responses")
    else:
        print("🚀 Real API mode is ENABLED - will make actual API calls")
    
    print()
    
    # Run tests
    tests = [
        ("Simulation Mode", test_simulate_mode),
        ("OpenAI API", test_openai_api),
        ("Multiple Providers", test_multiple_providers),
        ("Workflow Integration", test_workflow_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} test failed: {str(e)}")
            results[test_name] = False
        print()
    
    # Summary
    print("📋 Test Results Summary")
    print("-" * 30)
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASSED")
        elif result is False:
            print(f"❌ {test_name}: FAILED")
        else:
            print(f"⚠️  {test_name}: {result}")
    
    print()
    
    # Recommendations
    openai_success = results.get("OpenAI API", False)
    
    if openai_success:
        print("🎉 SUCCESS! Your OpenAI integration is working.")
        print("✅ You can now use AI nodes in your workflows with real API calls.")
    else:
        print("⚠️  OpenAI integration needs attention.")
        print("💡 Check your OPENAI_API_KEY and ensure SIMULATE=false")
    
    print("\n🎯 Next Steps:")
    print("1. Test your workflows in the frontend")
    print("2. Check backend logs for any API issues")
    print("3. Configure additional AI providers as needed")

if __name__ == "__main__":
    asyncio.run(main()) 
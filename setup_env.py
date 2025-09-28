#!/usr/bin/env python3
"""
Environment Setup Script for Workflow Automation
This script helps configure API keys for AI providers
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create or update .env file with API keys"""
    
    # Get the backend directory path
    backend_dir = Path(__file__).parent
    env_file = backend_dir / ".env"
    
    print("🚀 Workflow Automation - Environment Setup")
    print("=" * 50)
    print()
    
    # Check if .env file exists
    env_vars = {}
    if env_file.exists():
        print(f"Found existing .env file at: {env_file}")
        # Read existing variables
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
        print(f"Loaded {len(env_vars)} existing environment variables")
    else:
        print(f"Creating new .env file at: {env_file}")
    
    print()
    
    # API Keys to configure
    api_keys = {
        "OPENAI_API_KEY": {
            "description": "OpenAI API Key (for GPT models)",
            "example": "sk-proj-...",
            "required": True
        },
        "ANTHROPIC_API_KEY": {
            "description": "Anthropic API Key (for Claude models)",
            "example": "sk-ant-api...",
            "required": False
        },
        "GOOGLE_API_KEY": {
            "description": "Google API Key (for Gemini models)",
            "example": "AIza...",
            "required": False
        },
        "COHERE_API_KEY": {
            "description": "Cohere API Key (for Command models)",
            "example": "...",
            "required": False
        },
        "PERPLEXITY_API_KEY": {
            "description": "Perplexity API Key",
            "example": "pplx-...",
            "required": False
        },
        "XAI_API_KEY": {
            "description": "xAI API Key (for Grok models)",
            "example": "xai-...",
            "required": False
        },
        "AZURE_API_KEY": {
            "description": "Azure OpenAI API Key",
            "example": "...",
            "required": False
        },
        "AZURE_ENDPOINT": {
            "description": "Azure OpenAI Endpoint URL",
            "example": "https://your-resource.openai.azure.com/",
            "required": False
        }
    }
    
    # Configure API keys
    for key, config in api_keys.items():
        current_value = env_vars.get(key, "")
        
        print(f"📝 {config['description']}")
        
        if current_value:
            # Mask the current value for security
            masked_value = current_value[:8] + "..." + current_value[-4:] if len(current_value) > 12 else "***"
            print(f"   Current value: {masked_value}")
        
        if config["required"]:
            print(f"   ⚠️  REQUIRED for basic functionality")
        else:
            print(f"   Optional (for {key.split('_')[0]} provider)")
        
        print(f"   Example: {config['example']}")
        
        # Get user input
        prompt = f"   Enter {key}"
        if current_value:
            prompt += " (press Enter to keep current)"
        prompt += ": "
        
        new_value = input(prompt).strip()
        
        if new_value:
            env_vars[key] = new_value
            print(f"   ✅ {key} updated")
        elif not current_value and config["required"]:
            print(f"   ⚠️  Warning: {key} is required but not set")
        
        print()
    
    # Add other environment variables
    other_vars = {
        "SIMULATE": "false",  # Set to false for real API calls
        "DEBUG": "true",
        "MONGODB_URL": "mongodb://localhost:27017",
        "DATABASE_NAME": "workflow_automation",
        "REDIS_URL": "redis://localhost:6379",
        "SECRET_KEY": "your-secret-key-here",
        "FRONTEND_URL": "http://localhost:5174"
    }
    
    print("🔧 Other Configuration")
    print("-" * 30)
    
    for key, default_value in other_vars.items():
        if key not in env_vars:
            env_vars[key] = default_value
            print(f"   ✅ Set {key} = {default_value}")
    
    # Write the .env file
    print()
    print("💾 Writing .env file...")
    
    with open(env_file, 'w') as f:
        f.write("# AI Provider API Keys\n")
        for key in api_keys.keys():
            if key in env_vars:
                f.write(f"{key}={env_vars[key]}\n")
        
        f.write("\n# Application Configuration\n")
        for key, value in other_vars.items():
            f.write(f"{key}={env_vars.get(key, value)}\n")
        
        f.write("\n# Database Configuration\n")
        f.write("# Add your database URLs and other configs here\n")
    
    print(f"✅ Environment file created: {env_file}")
    print()
    
    # Validate setup
    validate_setup(env_vars)

def validate_setup(env_vars):
    """Validate the environment setup"""
    print("🔍 Validating Setup")
    print("-" * 20)
    
    # Check if OPENAI_API_KEY is set (most important for basic functionality)
    if env_vars.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key configured")
    else:
        print("⚠️  OpenAI API key not configured - AI nodes will use mock responses")
    
    # Check SIMULATE setting
    simulate = env_vars.get("SIMULATE", "false").lower()
    if simulate == "true":
        print("🔄 SIMULATE mode enabled - will use mock responses")
    else:
        print("🚀 Real API mode enabled - will make actual API calls")
    
    # Count configured providers
    providers = ["OPENAI", "ANTHROPIC", "GOOGLE", "COHERE", "PERPLEXITY", "XAI"]
    configured_count = sum(1 for p in providers if env_vars.get(f"{p}_API_KEY"))
    
    print(f"📊 Configured AI providers: {configured_count}/{len(providers)}")
    print()
    
    print("🎯 Next Steps:")
    print("1. Restart your backend server to load new environment variables")
    print("2. Test your workflow with AI nodes")
    print("3. Check logs for any API connection issues")
    print()
    
    if configured_count == 0:
        print("⚠️  No AI providers configured. Add at least OPENAI_API_KEY to use AI features.")
    elif env_vars.get("OPENAI_API_KEY"):
        print("✅ Ready to use AI features! Your OpenAI API key is configured.")

def main():
    """Main function"""
    try:
        create_env_file()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
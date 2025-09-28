# AI Integration Fix - Real API Calls

This fix replaces mock AI responses with real API calls to OpenAI, Anthropic, Google Gemini, Cohere, and other providers.

## 🚀 Quick Setup

### 1. Configure Environment Variables

Run the setup script to configure your API keys:

```bash
cd backend
python setup_env.py
```

This will:
- Create or update your `.env` file
- Guide you through setting up API keys
- Configure simulation mode settings

### 2. Test the Integration

Verify everything is working:

```bash
python test_real_apis.py
```

This will test:
- ✅ OpenAI API connection
- ✅ Simulation mode functionality
- ✅ Multiple provider support
- ✅ Workflow integration

### 3. Restart Your Backend

After configuring environment variables, restart your backend server:

```bash
# If using uvicorn directly
uvicorn main:app --reload

# Or your existing start script
python start_server.py
```

## 📝 Environment Variables

### Required for Basic Functionality
- `OPENAI_API_KEY` - Your OpenAI API key (starts with `sk-proj-` or `sk-`)

### Optional (Additional Providers)
- `ANTHROPIC_API_KEY` - For Claude models
- `GOOGLE_API_KEY` - For Gemini models  
- `COHERE_API_KEY` - For Command models
- `PERPLEXITY_API_KEY` - For Perplexity models
- `XAI_API_KEY` - For Grok models
- `AZURE_API_KEY` & `AZURE_ENDPOINT` - For Azure OpenAI

### Control Settings
- `SIMULATE=false` - Use real APIs (set to `true` for mock responses)
- `DEBUG=true` - Enable debug logging

## 🔧 What Was Fixed

### 1. Real API Calls (`ai_node_handlers.py`)
- ✅ Replaced `call_ai_api` mock function with real API integration
- ✅ Added support for OpenAI, Anthropic, Gemini, Cohere APIs
- ✅ Proper error handling and fallback to mock on errors
- ✅ Environment variable integration

### 2. Enhanced AI Providers (`ai_providers_node.py`)
- ✅ Updated `call_ai_api` to use real APIs
- ✅ Added individual API handler functions
- ✅ Improved variable processing and workflow integration
- ✅ Support for personal API keys in node configuration

### 3. Environment Management
- ✅ Created `setup_env.py` for easy configuration
- ✅ Added validation and testing tools
- ✅ Proper .env file structure

## 🎯 How to Use in Workflows

### 1. Global API Keys (Recommended)
Set your API keys in the `.env` file, and all AI nodes will use them automatically.

### 2. Per-Node API Keys
In your workflow canvas, you can:
- Add an AI node (OpenAI, Anthropic, etc.)
- Enable "Use Personal Key" option
- Enter your specific API key for that node

### 3. Simulation Mode
- Set `SIMULATE=true` in .env for testing/development
- Set `SIMULATE=false` for production with real API calls

## 🔍 Troubleshooting

### Mock Responses Still Appearing?
1. Check `SIMULATE` setting in .env (should be `false`)
2. Verify API key is correctly set
3. Restart your backend server
4. Check logs for API connection errors

### API Key Not Working?
1. Verify the key format matches the provider
2. Check rate limits and billing status
3. Test with the `test_real_apis.py` script
4. Review backend logs for specific error messages

### Variable Processing Issues?
- Ensure proper `{{variable}}` syntax in prompts
- Check that previous nodes are outputting expected values
- Use the workflow debugger to trace data flow

## 📊 Testing Commands

```bash
# Test all integrations
python test_real_apis.py

# Setup environment
python setup_env.py

# Test specific OpenAI connection
python test_openai_connection.py
```

## 🔄 Migration from Mock to Real

Your existing workflows will automatically use real APIs once:
1. ✅ Environment variables are configured
2. ✅ `SIMULATE=false` is set
3. ✅ Backend is restarted

No changes needed to existing workflow definitions!

## 🎉 Success Indicators

When working correctly, you should see:
- Real AI responses instead of template text
- Actual token usage in logs
- Provider-specific response formats
- Variable processing working with real content

## 📞 Support

If you encounter issues:
1. Check the backend logs for specific errors
2. Run `python test_real_apis.py` for diagnostics
3. Verify your API keys and billing status
4. Ensure all required packages are installed (`pip install -r requirements.txt`) 
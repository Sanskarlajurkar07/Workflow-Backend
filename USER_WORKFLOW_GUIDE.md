# User Workflow Guide: Complete Variable System

## Overview

Your workflow automation system now includes a **comprehensive variable system** that allows seamless data flow between nodes. This guide covers everything you need to know about creating workflows with proper variable handling.

## ✅ Fixed Issues

### 1. **Variable System Completely Implemented**
- Variables like `{{input_0.output}}` now work correctly
- AI responses properly substitute into templates  
- No more null/empty variable values

### 2. **API Key Independence**
- System works without requiring real API keys
- Mock responses for testing and development
- Realistic AI responses based on input content

### 3. **Consistent Field Names**
- Input nodes: use `.output` field (e.g., `{{input_0.output}}`)
- AI nodes: use `.response` field (e.g., `{{openai_0.response}}`)
- All nodes also support `.output` as a fallback

### 4. **Enhanced Variable Builder Frontend**
- Type `{{` to open variable builder automatically
- Smart suggestions based on connected nodes
- Real-time validation and error checking

## 🚀 Your Exact Workflow Now Works

### Workflow Structure:
```
[Input 0] → [OpenAI] → [Output]
[Input 1] →     ↑
```

### Configuration:
- **Input 0**: System instructions
- **Input 1**: User question  
- **OpenAI System Prompt**: `{{input_0.output}}`
- **OpenAI User Prompt**: `{{input_1.output}}`
- **Output Template**: `{{openai_0.response}}`

### Execution Flow:
1. `input_0.output` = "You are a helpful AI assistant..."
2. `input_1.output` = "What is the capital of France?"
3. OpenAI receives both prompts with real values (no templates)
4. OpenAI responds with actual answer about Paris
5. Output shows the AI's response, not `{{openai_0.response}}`

## 📝 Variable Syntax Guide

### Basic Format
```
{{nodeName.fieldName}}
```

### Common Field Names by Node Type

| Node Type | Primary Field | Alternative Fields |
|-----------|---------------|-------------------|
| Input | `.output` | `.text`, `.value` |
| OpenAI | `.response` | `.output`, `.content` |
| Anthropic | `.response` | `.output`, `.content` |
| Gemini | `.response` | `.output`, `.content` |
| Text Processor | `.output` | `.processed_text` |
| API Loader | `.response_data` | `.output` |
| Output | `.output` | `.value` |

### Examples

#### Simple Variable
```
{{input_0.output}}
```

#### Multiple Variables in Template
```
Question: {{input_1.output}}
Answer: {{openai_0.response}}
Processing time: {{openai_0.execution_time}}s
```

#### Conditional Content
```
Based on your query "{{user_question.output}}", here's what I found: {{search_results.response}}
```

## 🛠️ Using the Variable Builder

### Triggering the Builder
1. Click in any text field that supports variables
2. Type `{{` - the variable builder opens automatically
3. Or click the "Add Variable" button if available

### Selecting Variables
1. **Search**: Type to filter available variables
2. **Categories**: Variables grouped by type (Inputs, AI Models, etc.)
3. **Click to Insert**: Click any variable to insert it at cursor position

### Builder Features
- **Connected Nodes Only**: Shows only nodes connected to current node
- **Type Information**: Displays field types (Text, Number, etc.)
- **Descriptions**: Helpful descriptions for each field
- **Real-time Validation**: Warns about invalid variables

## 🎯 Best Practices

### 1. Node Naming
```javascript
// Good: Descriptive names
{
  "nodeName": "user_question",
  "nodeName": "system_instructions", 
  "nodeName": "ai_response"
}

// Variables become: {{user_question.output}}, {{ai_response.response}}
```

### 2. Workflow Structure
```
Input Nodes → Processing Nodes → Output Nodes
```

### 3. Variable Field Selection
- Use `.output` for most nodes (universal fallback)
- Use `.response` for AI nodes (more semantic)
- Use `.text` for text-specific content

### 4. Error Handling
- Connect nodes before referencing them in variables
- Use the variable builder to ensure correct syntax
- Check the preview to see resolved values

## 🔧 Technical Implementation

### Backend Enhancements
- **Variable Processor**: Enhanced regex-based substitution
- **Field Fallbacks**: Automatic fallback to compatible fields
- **Node Output Normalization**: Consistent field structure
- **Mock AI Responses**: Realistic responses without API keys

### Frontend Enhancements  
- **Enhanced Variable Builder**: Auto-triggered by `{{`
- **Real-time Validation**: Immediate feedback on variable errors
- **Smart Suggestions**: Context-aware variable recommendations
- **Type Safety**: Type-compatible field suggestions

## 📊 Testing Results

All tests now pass successfully:

### ✅ Variable Resolution Test
- `{{input_0.output}}` → Resolves to actual input text
- `{{input_1.output}}` → Resolves to actual input text  
- `{{openai_0.response}}` → Resolves to AI response
- Mixed variables work correctly
- Alternative field names supported

### ✅ Workflow Execution Test
- Input nodes execute successfully
- Variables properly substitute in AI prompts
- AI nodes receive real content, not templates
- Output nodes display final results
- End-to-end data flow verified

## 🚀 Quick Start Example

### 1. Create Your Workflow
```json
{
  "nodes": [
    {
      "id": "input_0",
      "type": "input", 
      "data": {
        "params": {
          "nodeName": "user_question"
        }
      }
    },
    {
      "id": "openai_0",
      "type": "openai",
      "data": {
        "params": {
          "nodeName": "ai_assistant",
          "prompt": "{{user_question.output}}",
          "system": "You are a helpful assistant."
        }
      }
    },
    {
      "id": "output_0", 
      "type": "output",
      "data": {
        "params": {
          "output": "{{ai_assistant.response}}"
        }
      }
    }
  ]
}
```

### 2. Connect the Nodes
```json
{
  "edges": [
    {
      "source": "input_0",
      "target": "openai_0"
    },
    {
      "source": "openai_0", 
      "target": "output_0"
    }
  ]
}
```

### 3. Test Execution
```bash
# Run the test script
cd backend
python test_user_workflow_fixed.py
```

## 🎉 Success Indicators

Your workflow is working correctly when you see:

1. **Variable Builder**: Opens when typing `{{`
2. **Connected Nodes**: Shows available variables from connected nodes
3. **Real Values**: Variables resolve to actual content, not template strings
4. **AI Responses**: Receive processed content, respond meaningfully
5. **Final Output**: Shows AI responses, not variable templates

## 🆘 Troubleshooting

### Issue: Variables not resolving
**Solution**: Ensure nodes are connected and have proper `nodeName` in params

### Issue: Variable builder not showing
**Solution**: Type `{{` in a text field or use "Add Variable" button

### Issue: AI responses seem generic
**Solution**: Check that variables are resolving - AI should receive real content

### Issue: Output shows templates instead of values
**Solution**: Verify variable syntax and node connections

## 🎯 Next Steps

1. **Test Your Workflow**: Use the provided test script
2. **Customize Responses**: Modify system prompts for better AI responses  
3. **Add More Nodes**: Expand workflow with additional processing steps
4. **Production Deployment**: Add real API keys when ready for production

---

**Your variable system is now fully functional!** 🎉

Variables like `{{input_0.output}}`, `{{input_1.output}}`, and `{{openai_0.response}}` will properly substitute actual values during workflow execution, giving you the automation system you wanted. 
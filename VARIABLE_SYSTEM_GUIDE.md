# Variable System User Guide

## Overview

The variable system allows you to reference outputs from other nodes in your workflow using the `{{node.field}}` syntax. This enables dynamic workflows where the output of one node becomes the input to another.

## How Variables Work

### Basic Syntax

Variables use double curly braces: `{{node_name.field_name}}`

Examples:
- `{{input_0.output}}` - References the output from input node 0
- `{{openai_0.response}}` - References the response from OpenAI node 0
- `{{text_processor_1.result}}` - References the result from text processor node 1

### Variable Resolution Process

1. **Node Execution**: When a node executes, its output is stored in the system
2. **Variable Detection**: The system scans text fields for `{{...}}` patterns
3. **Variable Substitution**: Each variable is replaced with the actual value from the referenced node
4. **Field Access**: If the specified field exists, its value is used; otherwise, it falls back to the main "output" field

## Supported Node Types and Fields

### Input Nodes
- `{{input_0.output}}` - The user-provided input value
- `{{input_1.output}}` - The user-provided input value for input node 1

### AI Provider Nodes (OpenAI, Anthropic, etc.)
- `{{openai_0.output}}` - The main AI response
- `{{openai_0.content}}` - Alternative access to the response
- `{{openai_0.response}}` - Another way to access the response
- `{{openai_0.model}}` - The model used
- `{{openai_0.provider}}` - The AI provider name

### Processing Nodes
- `{{text_processor_0.output}}` - Processed text result
- `{{json_handler_0.result}}` - JSON processing result
- `{{file_transformer_0.data}}` - Transformed file data

### Output Nodes
- `{{output_0.value}}` - The final output value
- `{{output_0.output}}` - Alternative access to the output

## Usage Examples

### Example 1: Basic Input to AI to Output

**Workflow Structure:**
1. Input Node (input_0) - User question
2. OpenAI Node (openai_0) - Process the question
3. Output Node (output_0) - Display the result

**Configuration:**
- **Input Node**: User enters "What is the capital of France?"
- **OpenAI Node Prompt**: `{{input_0.output}}`
- **Output Node Template**: `{{openai_0.output}}`

**Result Flow:**
1. input_0.output = "What is the capital of France?"
2. OpenAI receives: "What is the capital of France?"
3. OpenAI responds: "The capital of France is Paris."
4. Final output: "The capital of France is Paris."

### Example 2: System Prompt + User Prompt

**Workflow Structure:**
1. Input Node 0 (input_0) - User question
2. Input Node 1 (input_1) - System instructions
3. OpenAI Node (openai_0) - Process with both prompts
4. Output Node (output_0) - Display result

**Configuration:**
- **Input Node 0**: "What is the capital of France?"
- **Input Node 1**: "You are a helpful assistant. Provide detailed historical context."
- **OpenAI System Prompt**: `{{input_1.output}}`
- **OpenAI User Prompt**: `{{input_0.output}}`
- **Output Template**: `{{openai_0.output}}`

### Example 3: Complex Variable Combinations

**Template with Multiple Variables:**
```
Question: {{input_0.output}}
Instructions: {{input_1.output}}
AI Response: {{openai_0.output}}
Processing Time: {{openai_0.execution_time}}s
```

## Best Practices

### 1. Use Descriptive Node Names
- Name your nodes clearly: `user_question`, `system_instructions`, `ai_response`
- This makes variables more readable: `{{user_question.output}}`

### 2. Check Variable Availability
- Variables only work if the referenced node has already executed
- Ensure proper workflow order: inputs → processing → outputs

### 3. Handle Missing Variables
- If a variable doesn't exist, it remains unchanged in the text
- Example: `{{missing_node.output}}` stays as `{{missing_node.output}}`

### 4. Use Appropriate Field Names
- Most nodes have an `output` field as the main result
- AI nodes also have `content` and `response` fields
- Check node documentation for available fields

## Troubleshooting

### Variables Not Substituting

**Problem**: Variables remain as `{{node.field}}` instead of being replaced

**Solutions:**
1. **Check Node Execution Order**: Ensure the referenced node executes before the current node
2. **Verify Node ID**: Make sure the node ID matches exactly (case-sensitive)
3. **Check Field Name**: Verify the field exists (try `output` if unsure)
4. **Review Connections**: Ensure nodes are properly connected in the workflow

### Common Issues

#### Issue 1: Wrong Node Reference
```
❌ Wrong: {{Input_0.output}}  (wrong capitalization)
✅ Correct: {{input_0.output}}
```

#### Issue 2: Missing Field
```
❌ Wrong: {{openai_0.text}}  (field doesn't exist)
✅ Correct: {{openai_0.output}}
```

#### Issue 3: Circular References
```
❌ Wrong: Node A references Node B, Node B references Node A
✅ Correct: Linear flow: Input → Process → Output
```

## Advanced Usage

### Conditional Text with Variables

```
You asked: "{{input_0.output}}"

{{openai_0.output}}

This response was generated using {{openai_0.model}} in {{openai_0.execution_time}}s.
```

### Variable Validation

The system validates variables and will show warnings for:
- References to non-existent nodes
- Invalid field names
- Circular dependencies

## API Integration

When using the API, variables are processed automatically during workflow execution. No special handling is required from the client side.

### Example API Request

```json
{
  "inputs": {
    "input_0": {"value": "What is the capital of France?", "type": "Text"},
    "input_1": {"value": "Provide detailed historical context", "type": "Text"}
  }
}
```

The system will automatically:
1. Process input nodes
2. Substitute variables in AI prompts
3. Execute AI nodes with resolved prompts
4. Substitute variables in output nodes
5. Return final results

## Technical Details

### Variable Processing Engine

The variable system uses a dedicated `variable_processor.py` module that:

1. **Scans Text**: Finds all `{{...}}` patterns using regex
2. **Resolves References**: Looks up node outputs in the execution context
3. **Substitutes Values**: Replaces variables with actual values
4. **Handles Errors**: Gracefully handles missing nodes/fields

### Performance Considerations

- Variable processing is fast and optimized
- Variables are resolved once per node execution
- No significant performance impact on workflow execution

## Support

If you encounter issues with the variable system:

1. Check the workflow execution logs for variable resolution messages
2. Verify node connections and execution order
3. Test with simple variables first (`{{input_0.output}}`)
4. Gradually add complexity

The variable system is designed to be intuitive and robust, enabling powerful workflow automation with dynamic data flow between nodes. 
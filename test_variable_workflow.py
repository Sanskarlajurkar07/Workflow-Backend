import asyncio
import logging
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from variable_processor import process_node_variables, extract_variables_from_text, validate_variables

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_variable_processor():
    """Test the variable processor with different scenarios"""
    
    logger.info("=== Testing Variable Processor ===")
    
    # Mock node outputs as they would appear in a real workflow
    node_outputs = {
        "input-0": {
            "output": "What is the capital of France?",
            "type": "Text"
        },
        "input-1": {
            "output": "Please provide a detailed answer with historical context.",
            "type": "Text"
        },
        "openai-0": {
            "output": "The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum.",
            "content": "The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum.",
            "response": "The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum.",
            "model": "gpt-3.5-turbo",
            "provider": "openai"
        }
    }
    
    # Test cases for variable substitution
    test_cases = [
        {
            "name": "Basic node output reference",
            "template": "{{input-0.output}}",
            "expected": "What is the capital of France?"
        },
        {
            "name": "AI response reference",
            "template": "{{openai-0.output}}",
            "expected": "The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum."
        },
        {
            "name": "Combined template",
            "template": "Question: {{input-0.output}}\nAnswer: {{openai-0.output}}",
            "expected": "Question: What is the capital of France?\nAnswer: The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum."
        },
        {
            "name": "Alternative field access",
            "template": "{{openai-0.content}}",
            "expected": "The capital of France is Paris. This beautiful city has been the capital since 987 AD and is known for its rich history, culture, and landmarks like the Eiffel Tower and Louvre Museum."
        },
        {
            "name": "System prompt template",
            "template": "You are a helpful assistant. The user's context is: {{input-1.output}}",
            "expected": "You are a helpful assistant. The user's context is: Please provide a detailed answer with historical context."
        },
        {
            "name": "Invalid variable (should remain unchanged)",
            "template": "{{nonexistent.output}}",
            "expected": "{{nonexistent.output}}"
        },
        {
            "name": "Mixed valid and invalid",
            "template": "Valid: {{input-0.output}} Invalid: {{missing.field}}",
            "expected": "Valid: What is the capital of France? Invalid: {{missing.field}}"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"\n--- Testing: {test_case['name']} ---")
        logger.info(f"Template: {test_case['template']}")
        
        result = process_node_variables(test_case['template'], node_outputs)
        
        logger.info(f"Result: {result}")
        logger.info(f"Expected: {test_case['expected']}")
        
        success = result == test_case['expected']
        logger.info(f"Success: {success}")
        
        results.append({
            'name': test_case['name'],
            'success': success,
            'result': result,
            'expected': test_case['expected']
        })
    
    # Summary
    logger.info("\n=== Test Results Summary ===")
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    for result in results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        logger.info(f"{status}: {result['name']}")
        if not result['success']:
            logger.info(f"  Expected: {result['expected']}")
            logger.info(f"  Got: {result['result']}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    return passed == total

def test_variable_extraction():
    """Test variable extraction functionality"""
    
    logger.info("\n=== Testing Variable Extraction ===")
    
    test_cases = [
        {
            "text": "{{input-0.output}}",
            "expected": ["input-0.output"]
        },
        {
            "text": "Question: {{input-0.output}} Answer: {{openai-0.response}}",
            "expected": ["input-0.output", "openai-0.response"]
        },
        {
            "text": "No variables here",
            "expected": []
        },
        {
            "text": "{{var1}} and {{var2.field}} and {{var3.another.field}}",
            "expected": ["var1", "var2.field", "var3.another.field"]
        }
    ]
    
    for test_case in test_cases:
        result = extract_variables_from_text(test_case['text'])
        success = result == test_case['expected']
        
        logger.info(f"Text: {test_case['text']}")
        logger.info(f"Variables: {result}")
        logger.info(f"Expected: {test_case['expected']}")
        logger.info(f"Success: {success}\n")

def simulate_workflow_execution():
    """Simulate a complete workflow execution with variable processing"""
    
    logger.info("\n=== Simulating Complete Workflow Execution ===")
    
    # Define the workflow structure as described by the user
    workflow = {
        "nodes": [
            {
                "id": "input-0",
                "type": "input",
                "data": {"params": {"type": "Text", "nodeName": "Input 0"}}
            },
            {
                "id": "input-1", 
                "type": "input",
                "data": {"params": {"type": "Text", "nodeName": "Input 1"}}
            },
            {
                "id": "openai-0",
                "type": "openai",
                "data": {
                    "params": {
                        "model": "gpt-3.5-turbo",
                        "system": "{{input-1.output}}",
                        "prompt": "{{input-0.output}}",
                        "maxTokens": 1000,
                        "temperature": 0.7
                    }
                }
            },
            {
                "id": "output-0",
                "type": "output",
                "data": {
                    "params": {
                        "output": "{{openai-0.output}}",
                        "type": "Text"
                    }
                }
            }
        ],
        "edges": [
            {"source": "input-0", "target": "openai-0"},
            {"source": "input-1", "target": "openai-0"},
            {"source": "openai-0", "target": "output-0"}
        ]
    }
    
    # Simulate execution inputs
    execution_inputs = {
        "input_0": "What is the capital of France?",
        "input_1": "You are a helpful assistant. Provide detailed answers with historical context."
    }
    
    # Simulate the workflow execution step by step
    node_outputs = {}
    
    logger.info("Step 1: Processing input nodes")
    
    # Process input-0
    input0_output = {
        "output": execution_inputs["input_0"],
        "type": "Text"
    }
    node_outputs["input-0"] = input0_output
    logger.info(f"input-0 output: {input0_output}")
    
    # Process input-1
    input1_output = {
        "output": execution_inputs["input_1"],
        "type": "Text"
    }
    node_outputs["input-1"] = input1_output
    logger.info(f"input-1 output: {input1_output}")
    
    logger.info("\nStep 2: Processing OpenAI node")
    
    # Get OpenAI node parameters
    openai_node = workflow["nodes"][2]
    openai_params = openai_node["data"]["params"]
    
    # Process variables in the prompts
    system_prompt_template = openai_params["system"]
    user_prompt_template = openai_params["prompt"]
    
    logger.info(f"System prompt template: {system_prompt_template}")
    logger.info(f"User prompt template: {user_prompt_template}")
    
    # Apply variable substitution
    processed_system = process_node_variables(system_prompt_template, node_outputs)
    processed_user = process_node_variables(user_prompt_template, node_outputs)
    
    logger.info(f"Processed system prompt: {processed_system}")
    logger.info(f"Processed user prompt: {processed_user}")
    
    # Simulate OpenAI response
    openai_response = f"Based on your question '{processed_user}', the capital of France is Paris. This beautiful city has been the political and cultural center of France since 987 AD, when Hugh Capet made it the seat of the French monarchy. Paris is renowned for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums including the Louvre, and its influence on art, fashion, and cuisine throughout history."
    
    openai_output = {
        "output": openai_response,
        "content": openai_response,
        "response": openai_response,
        "model": "gpt-3.5-turbo",
        "provider": "openai",
        "system_prompt": processed_system,
        "user_prompt": processed_user
    }
    node_outputs["openai-0"] = openai_output
    logger.info(f"OpenAI output: {openai_response[:100]}...")
    
    logger.info("\nStep 3: Processing output node")
    
    # Get output node parameters
    output_node = workflow["nodes"][3]
    output_params = output_node["data"]["params"]
    
    output_template = output_params["output"]
    logger.info(f"Output template: {output_template}")
    
    # Process variables in output
    processed_output = process_node_variables(output_template, node_outputs)
    logger.info(f"Final output: {processed_output[:100]}...")
    
    # Verify the workflow worked correctly
    success = (
        processed_system == execution_inputs["input_1"] and
        processed_user == execution_inputs["input_0"] and
        processed_output == openai_response
    )
    
    logger.info(f"\n=== Workflow Simulation Result ===")
    logger.info(f"Success: {success}")
    logger.info(f"Variable substitution worked correctly: {success}")
    
    return success

def main():
    """Run all tests"""
    logger.info("Starting Variable System Tests")
    
    test1_passed = test_variable_processor()
    test_variable_extraction()
    test2_passed = simulate_workflow_execution()
    
    logger.info(f"\n=== FINAL RESULTS ===")
    logger.info(f"Variable Processor Test: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    logger.info(f"Workflow Simulation Test: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    overall_success = test1_passed and test2_passed
    logger.info(f"Overall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
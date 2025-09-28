#!/usr/bin/env python3
"""
Test script to verify the exact workflow scenario described by the user:
- 2 input nodes (input_0 and input_1)  
- 1 OpenAI node with {{input_0.output}} as user prompt and {{input_1.output}} as system prompt
- 1 output node with {{openai_0.output}}
"""

import sys
import os
import logging

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from variable_processor import process_node_variables

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_user_workflow_scenario():
    """Test the exact workflow scenario described by the user"""
    
    logger.info("🚀 Testing User's Workflow Scenario")
    logger.info("=" * 50)
    
    # Step 1: User provides inputs
    user_inputs = {
        "input_0": "What is the capital of France?",
        "input_1": "You are a helpful assistant. Provide detailed answers."
    }
    
    logger.info("📥 User Inputs:")
    logger.info(f"  • input_0: {user_inputs['input_0']}")
    logger.info(f"  • input_1: {user_inputs['input_1']}")
    logger.info("")
    
    # Step 2: Process input nodes
    node_outputs = {}
    
    # Input node outputs
    node_outputs["input_0"] = {"output": user_inputs["input_0"], "type": "Text"}
    node_outputs["input_1"] = {"output": user_inputs["input_1"], "type": "Text"}
    
    logger.info("✅ Input Nodes Processed")
    logger.info("")
    
    # Step 3: Process OpenAI node with variable substitution
    openai_config = {
        "system_prompt": "{{input_1.output}}",
        "user_prompt": "{{input_0.output}}",
        "model": "gpt-3.5-turbo"
    }
    
    logger.info("🤖 OpenAI Node Configuration:")
    logger.info(f"  • System Prompt Template: {openai_config['system_prompt']}")
    logger.info(f"  • User Prompt Template: {openai_config['user_prompt']}")
    logger.info("")
    
    # Apply variable substitution
    resolved_system_prompt = process_node_variables(openai_config["system_prompt"], node_outputs)
    resolved_user_prompt = process_node_variables(openai_config["user_prompt"], node_outputs)
    
    logger.info("🔄 Variable Substitution Results:")
    logger.info(f"  • Resolved System Prompt: {resolved_system_prompt}")
    logger.info(f"  • Resolved User Prompt: {resolved_user_prompt}")
    logger.info("")
    
    # Verify substitution worked correctly
    system_correct = resolved_system_prompt == user_inputs["input_1"]
    user_correct = resolved_user_prompt == user_inputs["input_0"]
    
    logger.info("✅ Variable Substitution Verification:")
    logger.info(f"  • System prompt correct: {system_correct}")
    logger.info(f"  • User prompt correct: {user_correct}")
    logger.info("")
    
    # Simulate OpenAI response
    mock_response = "The capital of France is Paris."
    node_outputs["openai_0"] = {
        "output": mock_response,
        "content": mock_response,
        "response": mock_response
    }
    
    # Step 4: Process output node
    output_template = "{{openai_0.output}}"
    final_output = process_node_variables(output_template, node_outputs)
    
    output_correct = final_output == mock_response
    
    logger.info("📤 Output Node:")
    logger.info(f"  • Template: {output_template}")
    logger.info(f"  • Final Output: {final_output}")
    logger.info(f"  • Output correct: {output_correct}")
    logger.info("")
    
    # Overall result
    all_correct = system_correct and user_correct and output_correct
    
    logger.info("🎯 FINAL RESULTS")
    logger.info("=" * 50)
    
    if all_correct:
        logger.info("🎉 ALL TESTS PASSED! 🎉")
        logger.info("The variable system works correctly!")
    else:
        logger.info("❌ SOME TESTS FAILED")
    
    return all_correct

def main():
    """Run the test"""
    logger.info("🧪 User Workflow Variable System Test")
    logger.info("=" * 70)
    logger.info("")
    
    success = test_user_workflow_scenario()
    
    if success:
        logger.info("")
        logger.info("🚀 Your workflow scenario will work correctly!")
        logger.info("✅ Variables like {{input_0.output}} are properly substituted")
        logger.info("✅ OpenAI prompts will receive the correct values")
        logger.info("✅ Output nodes will display AI responses correctly")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
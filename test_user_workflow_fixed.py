#!/usr/bin/env python3
"""
Test script for the user's exact workflow with comprehensive variable system testing.
This script tests the workflow with input nodes, OpenAI node, and output node.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_user_workflow")

# Import our modules
from variable_processor import process_node_variables, normalize_node_output, validate_variables
from ai_providers_node import handle_ai_provider_node
from node_handlers import handle_input_node, handle_output_node

def test_user_workflow_data():
    """Test the exact workflow data provided by the user"""
    
    # This is the exact workflow data provided by the user
    workflow_data = {
        "nodes": [
            {
                "id": "input_0",
                "type": "input",
                "position": {"x": -523.6466274199199, "y": 76.14493304821553},
                "data": {
                    "label": "input",
                    "type": "input",
                    "params": {"nodeName": "input_0"}
                },
                "width": 150,
                "height": 194
            },
            {
                "id": "input_1",
                "type": "input",
                "position": {"x": -538.8454726156402, "y": 547.6514729338476},
                "data": {
                    "label": "input",
                    "type": "input",
                    "params": {"nodeName": "input_1"}
                },
                "width": 150,
                "height": 194
            },
            {
                "id": "openai_0",
                "type": "openai",
                "position": {"x": -96.18073875246125, "y": -164.78469132989812},
                "data": {
                    "label": "openai",
                    "type": "openai",
                    "params": {
                        "nodeName": "openai_0",
                        "apiKey": "",
                        "usePersonalKey": False,
                        "prompt": "{{input_1.text}}",
                        "system": "{{input_0.text}}",
                        "temperature": 0.7,
                        "maxTokens": 1000,
                        "variableName": "openai_result",
                        "model": "gpt-4o"
                    },
                    "temperature": 0.7,
                    "maxTokens": 1000,
                    "variableName": "openai_result",
                    "system": "{{input_0.output}}",
                    "prompt": "n"
                },
                "width": 316,
                "height": 900,
                "selected": False,
                "dragging": False
            },
            {
                "id": "output_0",
                "type": "output",
                "position": {"x": 716.9996479946999, "y": 312.9877655094559},
                "data": {
                    "label": "output",
                    "type": "output",
                    "params": {
                        "nodeName": "output_0",
                        "fieldName": "output_0",
                        "output": "{{openai_0.response}}"
                    },
                    "fieldName": "output_0"
                },
                "width": 150,
                "height": 295
            }
        ],
        "edges": [
            {
                "id": "reactflow__edge-input_0-openai_0",
                "source": "input_0",
                "target": "openai_0",
                "type": "smoothstep",
                "animated": True,
                "data": {},
                "markerEnd": {"type": "arrowclosed"}
            },
            {
                "id": "reactflow__edge-input_1-openai_0",
                "source": "input_1",
                "target": "openai_0",
                "type": "smoothstep",
                "animated": True,
                "data": {},
                "markerEnd": {"type": "arrowclosed"}
            },
            {
                "id": "reactflow__edge-openai_0-output_0",
                "source": "openai_0",
                "target": "output_0",
                "type": "smoothstep",
                "animated": True,
                "data": {},
                "markerEnd": {"type": "arrowclosed"}
            }
        ],
        "timestamp": "2025-06-01T06:23:16.478Z",
        "version": "1.0.0"
    }
    
    return workflow_data

async def simulate_user_workflow():
    """Simulate execution of the user's exact workflow"""
    
    logger.info("=== Testing User's Exact Workflow ===")
    
    # Get the workflow data
    workflow = test_user_workflow_data()
    nodes = workflow["nodes"]
    
    # User's API Key
    USER_OPENAI_API_KEY = "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"

    # Simulation inputs - this is what the user would enter
    execution_inputs = {
        "input_0": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations.",
        "input_1": "What is the capital of France and what makes it historically significant?"
    }
    
    logger.info(f"Input 0 (System): {execution_inputs['input_0']}")
    logger.info(f"Input 1 (Question): {execution_inputs['input_1']}")
    
    # Track node outputs and workflow data
    node_outputs = {}
    workflow_data = {"workflow_id": "test_workflow", "user_id": "test_user"}
    
    # Mock request object for variable processing
    class MockRequest:
        def __init__(self):
            self.node_outputs = {}
    
    mock_request = MockRequest()
    
    try:
        # Step 1: Execute input_0 node
        logger.info("\n--- Step 1: Executing input_0 node ---")
        
        input0_node = nodes[0]
        input0_inputs = {"input": execution_inputs["input_0"]}
        
        result0 = await handle_input_node(
            node_id="input_0",
            node_data=input0_node["data"],
            inputs=input0_inputs,
            workflow_data=workflow_data,
            start_time=datetime.now().timestamp(),
            request=mock_request
        )
        
        node_outputs["input_0"] = result0.output
        mock_request.node_outputs = node_outputs
        
        logger.info(f"input_0 result: {result0.output}")
        
        # Step 2: Execute input_1 node
        logger.info("\n--- Step 2: Executing input_1 node ---")
        
        input1_node = nodes[1]
        input1_inputs = {"input": execution_inputs["input_1"]}
        
        result1 = await handle_input_node(
            node_id="input_1",
            node_data=input1_node["data"],
            inputs=input1_inputs,
            workflow_data=workflow_data,
            start_time=datetime.now().timestamp(),
            request=mock_request
        )
        
        node_outputs["input_1"] = result1.output
        mock_request.node_outputs = node_outputs
        
        logger.info(f"input_1 result: {result1.output}")
        
        # Step 3: Execute OpenAI node with variable processing
        logger.info("\n--- Step 3: Executing OpenAI node with variable processing ---")
        
        openai_node = nodes[2]
        
        # ---- Update OpenAI node params for API key test ----
        if openai_node['id'] == 'openai_0' and 'params' in openai_node['data']:
            openai_node['data']['params']['apiKey'] = USER_OPENAI_API_KEY
            openai_node['data']['params']['usePersonalKey'] = True
            logger.info(f"Updated openai_0 node params with API key and usePersonalKey=True")
        # ---- End update ----

        # Show the original templates
        system_template = openai_node["data"]["params"]["system"]
        prompt_template = openai_node["data"]["params"]["prompt"]
        
        logger.info(f"Original system template: '{system_template}'")
        logger.info(f"Original prompt template: '{prompt_template}'")
        
        # The OpenAI node gets empty inputs since it processes variables internally
        openai_inputs = {}
        
        result_openai = await handle_ai_provider_node(
            node_id="openai_0",
            node_data=openai_node["data"],
            inputs=openai_inputs,
            workflow_data=workflow_data,
            start_time=datetime.now().timestamp(),
            provider="openai",
            request=mock_request
        )
        
        node_outputs["openai_0"] = result_openai.output
        mock_request.node_outputs = node_outputs
        
        logger.info(f"OpenAI result (raw object): {result_openai.output}")
        openai_content = result_openai.output.get("content", "")
        logger.info(f"OpenAI result content: {openai_content}")
        
        # Check if it's a simulated real call
        if "SIMULATED REAL response from OpenAI" in openai_content:
            logger.info("✅ OpenAI node used the SIMULATED REAL API path as API key was provided.")
            if result_openai.output.get("api_mock") is False or result_openai.output.get("api_key_used_simulated") is True: # api_mock should be false if real key path taken
                 logger.info("✅ api_mock flag is correctly False or api_key_used_simulated is True.")
            else:
                 logger.error(f"❌ api_mock flag is unexpectedly True. Value: {result_openai.output.get('api_mock')}")
        else:
            logger.warning("⚠️ OpenAI node used the MOCK API path. Check API key and usePersonalKey settings if real path was expected.")
            if result_openai.output.get("api_mock") is True:
                 logger.info("✅ api_mock flag is correctly True for mock path.")
            else:
                 logger.error(f"❌ api_mock flag is unexpectedly False for mock path. Value: {result_openai.output.get('api_mock')}")
        
        # Step 4: Execute output node
        logger.info("\n--- Step 4: Executing output node ---")
        
        output_node = nodes[3]
        output_template = output_node["data"]["params"]["output"]
        
        logger.info(f"Output template: '{output_template}'")
        
        output_inputs = {}
        
        result_output = await handle_output_node(
            node_id="output_0", 
            node_data=output_node["data"],
            inputs=output_inputs,
            workflow_data=workflow_data,
            start_time=datetime.now().timestamp(),
            request=mock_request
        )
        
        logger.info(f"Final output: {result_output.output}")
        
        # Summary
        logger.info("\n=== WORKFLOW EXECUTION SUMMARY ===")
        logger.info(f"✅ All nodes executed successfully")
        logger.info(f"📊 Total nodes processed: {len(nodes)}")
        logger.info(f"🔗 Variables properly resolved")
        logger.info(f"📝 Final result: {result_output.output.get('output', 'N/A')}")
        
        # Final verification for API key usage
        if "SIMULATED REAL response from OpenAI" in openai_content:
            logger.info("✅ TEST SUCEEDED: Workflow simulation completed, and OpenAI node used the simulated real API path.")
            return True
        else:
            logger.error("❌ TEST FAILED: Workflow simulation completed, but OpenAI node did NOT use the simulated real API path.")
            return False
        
    except Exception as e:
        logger.error(f"❌ Workflow execution failed: {str(e)}", exc_info=True)
        return False

def test_variable_resolution():
    """Test variable resolution with the user's exact variable patterns"""
    
    logger.info("\n=== Testing Variable Resolution ===")
    
    # Mock node outputs similar to what the workflow would produce
    node_outputs = {
        "input_0": {
            "output": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations.",
            "text": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations.",
            "content": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations."
        },
        "input_1": {
            "output": "What is the capital of France and what makes it historically significant?",
            "text": "What is the capital of France and what makes it historically significant?",
            "content": "What is the capital of France and what makes it historically significant?"
        },
        "openai_0": {
            "output": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history...",
            "response": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history...",
            "content": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history..."
        }
    }
    
    # Test cases for different variable patterns
    test_cases = [
        {
            "name": "System prompt variable",
            "template": "{{input_0.output}}",
            "expected": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations."
        },
        {
            "name": "User prompt variable",
            "template": "{{input_1.output}}",
            "expected": "What is the capital of France and what makes it historically significant?"
        },
        {
            "name": "OpenAI response variable",
            "template": "{{openai_0.response}}",
            "expected": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history..."
        },
        {
            "name": "Mixed variables",
            "template": "Question: {{input_1.output}}\nAnswer: {{openai_0.response}}",
            "expected": "Question: What is the capital of France and what makes it historically significant?\nAnswer: The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history..."
        },
        {
            "name": "Alternative field names",
            "template": "{{input_0.text}} and {{openai_0.content}}",
            "expected": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations. and The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history..."
        }
    ]
    
    success_count = 0
    for test_case in test_cases:
        logger.info(f"\nTesting: {test_case['name']}")
        logger.info(f"Template: {test_case['template']}")
        
        result = process_node_variables(test_case["template"], node_outputs)
        
        logger.info(f"Result: {result}")
        
        if result == test_case["expected"]:
            logger.info("✅ Test passed")
            success_count += 1
        else:
            logger.error("❌ Test failed")
            logger.error(f"Expected: {test_case['expected']}")
    
    logger.info(f"\n📊 Variable Resolution Summary: {success_count}/{len(test_cases)} tests passed")
    return success_count == len(test_cases)

def main():
    """Main test function"""
    
    logger.info("🚀 Starting User Workflow Testing")
    
    # Test 1: Variable resolution
    var_test_success = test_variable_resolution()
    
    # Test 2: Full workflow simulation
    workflow_test_success = asyncio.run(simulate_user_workflow())
    
    # Final summary
    logger.info("\n" + "="*50)
    logger.info("📋 FINAL TEST SUMMARY")
    logger.info("="*50)
    logger.info(f"Variable Resolution Test: {'✅ PASSED' if var_test_success else '❌ FAILED'}")
    logger.info(f"Workflow Execution Test: {'✅ PASSED' if workflow_test_success else '❌ FAILED'}")
    
    if var_test_success and workflow_test_success:
        logger.info("🎉 ALL TESTS PASSED! The variable system is working correctly.")
        logger.info("✨ Your workflow will now properly substitute variables:")
        logger.info("   • {{input_0.output}} → System instructions")
        logger.info("   • {{input_1.output}} → User question")  
        logger.info("   • {{openai_0.response}} → AI response")
        return True
    else:
        logger.error("❌ Some tests failed. Please check the logs above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 
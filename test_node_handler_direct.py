#!/usr/bin/env python3
"""
Direct test of handle_node function to reproduce the NameError
"""

import asyncio
import sys
import os

# Add the current directory to Python path so we can import modules
sys.path.insert(0, os.path.dirname(__file__))

async def test_handle_input_node():
    """Test the handle_node function directly with an input node"""
    try:
        # Import the function we want to test
        from node_handlers import handle_node, NODE_HANDLERS
        
        print("Testing handle_node function directly...")
        print(f"NODE_HANDLERS keys: {list(NODE_HANDLERS.keys())}")
        
        if "input" in NODE_HANDLERS:
            print(f"handle_input_node is available: {NODE_HANDLERS['input']}")
            print(f"Type: {type(NODE_HANDLERS['input'])}")
            print(f"Callable: {callable(NODE_HANDLERS['input'])}")
        else:
            print("ERROR: 'input' handler not found in NODE_HANDLERS!")
            return
        
        # Test data for an input node
        node_id = "input-0"
        node_type = "input"
        node_data = {
            "params": {
                "fieldName": "test_input",
                "type": "Text"
            }
        }
        inputs = {
            "input": "Hello, this is a test input!",
            "type": "Text"
        }
        workflow_data = {}
        
        print(f"\nCalling handle_node with:")
        print(f"  node_id: {node_id}")
        print(f"  node_type: {node_type}")
        print(f"  node_data: {node_data}")
        print(f"  inputs: {inputs}")
        
        # Call the function
        result = await handle_node(
            node_id=node_id,
            node_type=node_type,
            node_data=node_data,
            inputs=inputs,
            workflow_data=workflow_data,
            request=None
        )
        
        print(f"\nResult: {result}")
        print(f"Result status: {result.status}")
        
        if result.status == "success":
            print("✅ Test PASSED: handle_input_node worked correctly!")
        else:
            print(f"❌ Test FAILED: {result.message}")
            
        # Test output node handler
        print("\n--- Testing Output Node Handler ---")
        print("Calling handle_node with output node:")
        print("  node_id: output-0")
        print("  node_type: output")
        print("  node_data: {'params': {'output': '{{input_0.output}}', 'type': 'Text', 'fieldName': 'result'}}")
        print("  inputs: {'input': 'This is test output data'}")
        
        result = await handle_node(
            node_id="output-0",
            node_type="output", 
            node_data={"params": {"output": "{{input_0.output}}", "type": "Text", "fieldName": "result"}},
            inputs={"input": "This is test output data"},
            workflow_data={}
        )
        print(f"Result: {result}")
        print(f"Result status: {result.status}")
        
        if result.status == "success" and result.output:
            print("✅ Test PASSED: handle_output_node worked correctly!")
        else:
            print("❌ Test FAILED: handle_output_node did not work as expected")
            
    except Exception as e:
        print(f"❌ Test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_handle_input_node()) 
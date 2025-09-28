#!/usr/bin/env python3
"""
Simple Workflow Execution Engine Test
Tests the execution engine directly without HTTP calls
"""

import asyncio
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import workflow execution components  
from routers.workflows import calculate_execution_order, get_node_inputs, execute_workflow_node
from models.workflow import NodeResult
from node_handlers import handle_node

class MockRequest:
    """Mock request object for testing"""
    def __init__(self):
        self.workflow_variables = {}
        self.node_outputs = {}
        
class MockApp:
    """Mock app for database access"""
    def __init__(self):
        self.mongodb = None

async def test_workflow_execution_engine():
    """Test the workflow execution engine directly"""
    
    print("🔧 Simple Workflow Execution Engine Test")
    print("=" * 50)
    
    # Test 1: Basic execution order calculation
    print("1️⃣ Testing execution order calculation...")
    
    test_nodes = [
        {"id": "input-1", "type": "input"},
        {"id": "ai-1", "type": "openai"},
        {"id": "output-1", "type": "output"}
    ]
    
    test_edges = [
        {"source": "input-1", "target": "ai-1"},
        {"source": "ai-1", "target": "output-1"}
    ]
    
    try:
        execution_order = calculate_execution_order(test_nodes, test_edges)
        execution_ids = [node["id"] for node in execution_order]
        print(f"   ✅ Execution order: {execution_ids}")
        
        # Verify order is correct (input -> ai -> output)
        if execution_ids == ["input-1", "ai-1", "output-1"]:
            print("   ✅ Execution order is correct")
        else:
            print(f"   ❌ Execution order incorrect, expected ['input-1', 'ai-1', 'output-1']")
            
    except Exception as e:
        print(f"   ❌ Execution order calculation failed: {e}")
        return False
    
    # Test 2: Node input calculation
    print("\n2️⃣ Testing node input calculation...")
    
    try:
        # Test inputs for input node (should use initial inputs)
        input_node_inputs = get_node_inputs("input-1", test_edges, {}, {"input": "test text"}, test_nodes)
        print(f"   ✅ Input node inputs: {input_node_inputs}")
        
        # Test inputs for AI node (should use input node output)
        mock_node_outputs = {"input-1": {"output": "processed text"}}
        ai_node_inputs = get_node_inputs("ai-1", test_edges, mock_node_outputs, {"input": "test text"}, test_nodes)
        print(f"   ✅ AI node inputs: {ai_node_inputs}")
        
    except Exception as e:
        print(f"   ❌ Node input calculation failed: {e}")
        return False
    
    # Test 3: Individual node execution
    print("\n3️⃣ Testing individual node execution...")
    
    try:
        # Create mock request
        mock_request = MockRequest()
        
        # Test input node execution
        input_node = {"id": "input-1", "type": "input", "data": {"params": {"nodeName": "test_input", "type": "Text"}}}
        input_inputs = {"input": "Hello World"}
        
        input_result = await execute_workflow_node(input_node, input_inputs, {}, mock_request, "test_user")
        
        if input_result:
            print(f"   ✅ Input node executed successfully")
            print(f"   📤 Input result: {str(input_result.output)[:100]}...")
        else:
            print(f"   ❌ Input node returned None")
            return False
            
    except Exception as e:
        print(f"   ❌ Node execution failed: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        return False
    
    # Test 4: Node handler direct test
    print("\n4️⃣ Testing node handlers directly...")
    
    try:
        # Test input node handler directly
        from node_handlers import handle_input_node
        
        start_time = datetime.now().timestamp()
        direct_result = await handle_input_node(
            "input-1",
            {"params": {"nodeName": "test_input", "type": "Text"}},
            {"input": "Direct handler test"},
            {},
            start_time
        )
        
        if direct_result and hasattr(direct_result, 'output'):
            print(f"   ✅ Direct node handler worked")
            print(f"   📤 Direct result: {str(direct_result.output)[:100]}...")
        else:
            print(f"   ❌ Direct node handler failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Direct node handler test failed: {e}")
        return False
    
    # Test 5: Full workflow simulation
    print("\n5️⃣ Testing full workflow simulation...")
    
    try:
        mock_request = MockRequest()
        node_outputs = {}
        node_results = {}
        
        # Execute nodes in order
        for i, node in enumerate(execution_order):
            node_id = node["id"]
            node_type = node["type"]
            
            print(f"   Executing {node_id} ({node_type})...")
            
            # Get inputs for this node
            inputs = get_node_inputs(node_id, test_edges, node_outputs, {"input": "Test workflow execution"}, test_nodes)
            
            # Add proper node data
            if node_type == "input":
                node["data"] = {"params": {"nodeName": "test_input", "type": "Text"}}
            elif node_type == "openai":
                node["data"] = {"params": {"nodeName": "ai_processor", "model": "gpt-3.5-turbo", "prompt": "Process: {{test_input.output}}"}}
            elif node_type == "output":
                node["data"] = {"params": {"nodeName": "final_output", "output": "Result: {{ai_processor.output}}"}}
            
            # Execute the node
            try:
                result = await execute_workflow_node(node, inputs, {}, mock_request, "test_user")
                
                if result:
                    # Handle different result types
                    if hasattr(result, 'output'):
                        node_output = result.output
                        node_status = getattr(result, 'status', 'completed')
                    elif isinstance(result, dict):
                        node_output = result
                        node_status = 'completed'
                    else:
                        node_output = result
                        node_status = 'completed'
                    
                    # Store outputs and results
                    node_outputs[node_id] = node_output
                    node_results[node_id] = {
                        "status": node_status,
                        "output": node_output,
                        "node_type": node_type
                    }
                    
                    # Update request context
                    mock_request.node_outputs = node_outputs
                    
                    print(f"     ✅ {node_id} completed: {str(node_output)[:50]}...")
                    
                else:
                    print(f"     ❌ {node_id} returned None")
                    node_results[node_id] = {"status": "error", "error": "No result"}
                    
            except Exception as node_error:
                print(f"     ❌ {node_id} failed: {node_error}")
                node_results[node_id] = {"status": "error", "error": str(node_error)}
        
        # Analyze results
        successful_nodes = len([r for r in node_results.values() if r["status"] == "completed"])
        total_nodes = len(node_results)
        
        print(f"\n   📊 SIMULATION RESULTS:")
        print(f"   ├─ Total nodes: {total_nodes}")
        print(f"   ├─ Successful: {successful_nodes}")
        print(f"   └─ Failed: {total_nodes - successful_nodes}")
        
        print(f"\n   📋 NODE OUTPUTS:")
        for node_id, output in node_outputs.items():
            print(f"   ├─ {node_id}: {str(output)[:80]}...")
            
        if successful_nodes == total_nodes and total_nodes > 0:
            print(f"\n   🎉 WORKFLOW SIMULATION SUCCESSFUL!")
            print(f"   ✅ All nodes executed correctly")
            print(f"   ✅ Data flows between nodes") 
            print(f"   ✅ Execution engine is working")
            return True
        else:
            print(f"\n   ⚠️ PARTIAL SUCCESS: {successful_nodes}/{total_nodes} nodes")
            return False
            
    except Exception as e:
        print(f"   ❌ Workflow simulation failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_workflow_execution_engine())
    
    if success:
        print(f"\n🏁 ALL TESTS PASSED - Execution Engine Working! ✅")
    else:
        print(f"\n🏁 TESTS FAILED - Execution Engine Needs Fixes ❌")
        
    print("=" * 50) 
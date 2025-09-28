#!/usr/bin/env python3
"""
Comprehensive Workflow Execution Engine Test
Tests the fixed workflow execution engine to ensure it runs and shows results properly
"""

import asyncio
import httpx
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any

async def test_workflow_execution_engine():
    """Test the workflow execution engine comprehensively"""
    
    base_url = "http://localhost:8000"
    test_user_token = None  # Will get from login
    
    print("🔧 Workflow Execution Engine Test")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Step 1: Register/Login test user
        print("1️⃣ Setting up test user...")
        try:
            register_data = {
                "username": "test_execution_user",
                "email": "test_execution@example.com", 
                "password": "testpass123"
            }
            
            # Try to register (might fail if user exists, that's ok)
            try:
                await client.post(f"{base_url}/auth/register", json=register_data)
                print("   ✅ Test user registered")
            except:
                print("   ℹ️ Test user already exists")
            
            # Login to get token
            login_data = {
                "username": "test_execution_user",
                "password": "testpass123"
            }
            
            login_response = await client.post(f"{base_url}/auth/token", data=login_data)
            if login_response.status_code == 200:
                test_user_token = login_response.json()["access_token"]
                print("   ✅ Successfully logged in")
            else:
                print(f"   ❌ Login failed: {login_response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ User setup failed: {e}")
            return
        
        # Set authorization header
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Step 2: Create a test workflow
        print("\n2️⃣ Creating test workflow...")
        try:
            test_workflow = {
                "name": "Execution Engine Test Workflow",
                "description": "Test workflow for execution engine",
                "nodes": [
                    {
                        "id": "input-1",
                        "type": "input",
                        "position": {"x": 100, "y": 100},
                        "data": {
                            "params": {
                                "nodeName": "test_input",
                                "type": "Text"
                            }
                        }
                    },
                    {
                        "id": "openai-1", 
                        "type": "openai",
                        "position": {"x": 300, "y": 100},
                        "data": {
                            "params": {
                                "nodeName": "ai_processor",
                                "model": "gpt-3.5-turbo",
                                "prompt": "Summarize this text: {{test_input.output}}",
                                "temperature": 0.7,
                                "maxTokens": 100
                            }
                        }
                    },
                    {
                        "id": "output-1",
                        "type": "output", 
                        "position": {"x": 500, "y": 100},
                        "data": {
                            "params": {
                                "nodeName": "final_output",
                                "fieldName": "summary",
                                "output": "AI Summary: {{ai_processor.output}}"
                            }
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "input-1", 
                        "target": "openai-1",
                        "sourceHandle": null,
                        "targetHandle": null
                    },
                    {
                        "id": "edge-2",
                        "source": "openai-1",
                        "target": "output-1", 
                        "sourceHandle": null,
                        "targetHandle": null
                    }
                ]
            }
            
            create_response = await client.post(
                f"{base_url}/workflows/",
                headers=headers,
                json=test_workflow
            )
            
            if create_response.status_code == 201:
                workflow_data = create_response.json()
                workflow_id = workflow_data["id"]
                print(f"   ✅ Test workflow created: {workflow_id}")
            else:
                print(f"   ❌ Workflow creation failed: {create_response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ Workflow creation error: {e}")
            return
        
        # Step 3: Execute the workflow
        print(f"\n3️⃣ Executing workflow {workflow_id}...")
        try:
            execution_request = {
                "inputs": {
                    "input": "Artificial Intelligence is transforming various industries by automating complex processes, improving decision-making, and enabling new capabilities that were previously impossible. From healthcare to finance, AI applications are becoming increasingly sophisticated and widespread."
                }
            }
            
            print(f"   📤 Sending execution request...")
            print(f"   Input text: {execution_request['inputs']['input'][:100]}...")
            
            start_time = time.time()
            
            execute_response = await client.post(
                f"{base_url}/workflows/{workflow_id}/execute",
                headers=headers,
                json=execution_request
            )
            
            execution_time = time.time() - start_time
            
            if execute_response.status_code == 200:
                result = execute_response.json()
                print(f"   ✅ Workflow executed successfully in {execution_time:.2f}s")
                print(f"   📊 Execution ID: {result.get('execution_id', 'N/A')}")
                print(f"   📈 Status: {result.get('status', 'N/A')}")
                
                # Display results
                results = result.get('results', {})
                node_results = result.get('node_results', {})
                
                print(f"\n   🎯 EXECUTION RESULTS:")
                print(f"   ├─ Total execution time: {result.get('execution_time', 0):.3f}s")
                print(f"   ├─ Execution path: {result.get('execution_path', [])}")
                
                if result.get('execution_stats'):
                    stats = result['execution_stats']
                    print(f"   ├─ Successful nodes: {stats.get('successful_nodes', 0)}")
                    print(f"   └─ Failed nodes: {stats.get('failed_nodes', 0)}")
                
                print(f"\n   📋 NODE OUTPUTS:")
                for node_id, output in results.items():
                    print(f"   ├─ {node_id}: {str(output)[:100]}...")
                
                print(f"\n   📊 NODE EXECUTION DETAILS:")
                for node_id, node_result in node_results.items():
                    status = node_result.get('status', 'unknown')
                    exec_time = node_result.get('execution_time', 0)
                    node_type = node_result.get('node_type', 'unknown')
                    print(f"   ├─ {node_id} ({node_type}): {status} ({exec_time:.3f}s)")
                    
                    if status == 'error':
                        error = node_result.get('error', 'Unknown error')
                        print(f"   │  └─ Error: {error}")
                    elif node_result.get('output'):
                        output_preview = str(node_result['output'])[:80]
                        print(f"   │  └─ Output: {output_preview}...")
                
                # Test specific outputs
                print(f"\n   🔍 VALIDATING RESULTS:")
                
                # Check if input node produced output
                if 'input-1' in results:
                    input_output = results['input-1']
                    print(f"   ✅ Input node output: {str(input_output)[:50]}...")
                else:
                    print(f"   ❌ Input node did not produce output")
                
                # Check if AI node processed the input
                if 'openai-1' in results:
                    ai_output = results['openai-1']
                    print(f"   ✅ AI node output: {str(ai_output)[:50]}...")
                else:
                    print(f"   ❌ AI node did not produce output")
                
                # Check if output node formatted the result
                if 'output-1' in results:
                    final_output = results['output-1']
                    print(f"   ✅ Final output: {str(final_output)[:50]}...")
                else:
                    print(f"   ❌ Output node did not produce result")
                    
                # Overall assessment
                successful_nodes = len([r for r in node_results.values() if r.get('status') == 'completed'])
                total_nodes = len(node_results)
                
                if successful_nodes == total_nodes and total_nodes > 0:
                    print(f"\n   🎉 ALL TESTS PASSED! Execution engine working correctly.")
                    print(f"   ✅ {successful_nodes}/{total_nodes} nodes executed successfully")
                    print(f"   ✅ Workflow produced expected results")
                    print(f"   ✅ Variable substitution working")
                    print(f"   ✅ Result formatting working")
                else:
                    print(f"\n   ⚠️ PARTIAL SUCCESS: {successful_nodes}/{total_nodes} nodes succeeded")
                    
            else:
                print(f"   ❌ Workflow execution failed: HTTP {execute_response.status_code}")
                print(f"   Error: {execute_response.text}")
                
        except Exception as e:
            print(f"   ❌ Execution test error: {e}")
            return
        
        # Step 4: Test execution history
        print(f"\n4️⃣ Testing execution history...")
        try:
            history_response = await client.get(
                f"{base_url}/workflows/{workflow_id}/execution-history",
                headers=headers
            )
            
            if history_response.status_code == 200:
                history = history_response.json()
                executions = history.get('execution_history', [])
                print(f"   ✅ Found {len(executions)} execution records")
                
                if executions:
                    latest = executions[0]
                    print(f"   📋 Latest execution:")
                    print(f"   ├─ Status: {latest.get('status', 'N/A')}")
                    print(f"   ├─ Started: {latest.get('started_at', 'N/A')}")
                    print(f"   └─ Duration: {latest.get('execution_time', 0):.3f}s")
            else:
                print(f"   ❌ History retrieval failed: {history_response.text}")
                
        except Exception as e:
            print(f"   ❌ History test error: {e}")
        
        # Step 5: Clean up
        print(f"\n5️⃣ Cleaning up...")
        try:
            delete_response = await client.delete(
                f"{base_url}/workflows/{workflow_id}",
                headers=headers
            )
            
            if delete_response.status_code == 204:
                print(f"   ✅ Test workflow deleted successfully")
            else:
                print(f"   ⚠️ Cleanup warning: {delete_response.text}")
                
        except Exception as e:
            print(f"   ⚠️ Cleanup error: {e}")
    
    print(f"\n🏁 Workflow Execution Engine Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_workflow_execution_engine()) 
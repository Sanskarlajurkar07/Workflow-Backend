#!/usr/bin/env python3
"""
Test script to trigger workflow execution and debug the handle_input_node error
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def create_test_workflow():
    """Create a simple test workflow with an input node"""
    workflow_data = {
        "name": "Test Input Node Workflow",
        "description": "Simple workflow to test input node execution",
        "nodes": [
            {
                "id": "input-0",
                "type": "input",
                "position": {"x": 100, "y": 100},
                "data": {
                    "params": {
                        "fieldName": "test_input",
                        "type": "Text"
                    }
                }
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1}
    }
    
    response = requests.post(f"{BASE_URL}/api/workflows/", json=workflow_data)
    print(f"Create workflow response: {response.status_code}")
    if response.status_code == 201:
        workflow = response.json()
        print(f"Created workflow with ID: {workflow['id']}")
        return workflow['id']
    else:
        print(f"Error creating workflow: {response.text}")
        return None

def execute_workflow(workflow_id):
    """Execute the test workflow"""
    execution_data = {
        "inputs": {
            "input_0": "Hello, this is a test input!"
        }
    }
    
    print(f"Executing workflow {workflow_id} with inputs: {execution_data}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/workflows/{workflow_id}/execute", 
            json=execution_data,
            timeout=30
        )
        print(f"Execute response status: {response.status_code}")
        print(f"Execute response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("Workflow executed successfully!")
            print(json.dumps(result, indent=2))
        else:
            print(f"Workflow execution failed: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def main():
    print("Testing workflow execution to trigger handle_input_node error...")
    
    # Create test workflow
    workflow_id = create_test_workflow()
    
    if workflow_id:
        print(f"Waiting 2 seconds before execution...")
        time.sleep(2)
        
        # Execute workflow
        execute_workflow(workflow_id)
    else:
        print("Failed to create test workflow")

if __name__ == "__main__":
    main() 
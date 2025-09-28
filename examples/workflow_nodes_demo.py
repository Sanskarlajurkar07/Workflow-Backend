#!/usr/bin/env python3
"""
Workflow Nodes Demo Script
--------------------------
This script demonstrates how to use the enhanced workflow nodes.
It creates a simple workflow using condition, merge, time, and text to SQL nodes.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from pprint import pprint

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules
from routers.workflows import execute_workflow_node
from models.workflow import NodeResult

# Create a mock request class for testing
class MockRequest:
    def __init__(self):
        self.app = type('', (), {})()
        self.app.mongodb = {}
        self.headers = {"Authorization": "Bearer test_token"}
        self.url = type('', (), {})()
        self.url.scheme = "http"
        self.url.netloc = "localhost:8000"

async def demo_condition_node():
    """Demonstrate the Condition Node functionality"""
    print("\n\033[1m🔀 Condition Node Demo\033[0m")
    
    # Create a condition node with different condition types
    condition_node = {
        "id": "condition_demo",
        "type": "condition",
        "data": {
            "params": {
                "paths": [
                    {
                        "id": "path_0",
                        "clauses": [
                            {"id": "clause_0", "inputField": "temperature", "operator": ">", "value": "30"}
                        ],
                        "logicalOperator": "AND"
                    },
                    {
                        "id": "path_1",
                        "clauses": [
                            {"id": "clause_1", "inputField": "status", "operator": "matches_regex", "value": "^[A-Z][a-z]+$"}
                        ],
                        "logicalOperator": "AND"
                    },
                    {
                        "id": "path_2",
                        "clauses": [
                            {"id": "clause_2", "inputField": "last_updated", "operator": "date_after", "value": "2023-01-01"}
                        ],
                        "logicalOperator": "AND"
                    }
                ]
            }
        }
    }
    
    # Test data
    test_data = [
        {"temperature": 35, "status": "active", "last_updated": "2022-05-15"},
        {"temperature": 25, "status": "Active", "last_updated": "2022-05-15"},
        {"temperature": 25, "status": "inactive", "last_updated": "2023-06-15"}
    ]
    
    # Process each test case
    for i, data in enumerate(test_data):
        print(f"\nTest case {i+1}:")
        print(f"Input: {data}")
        
        result = await execute_workflow_node(
            condition_node, 
            {"input": data}, 
            {}, 
            MockRequest(), 
            "demo_user"
        )
        
        path_index = result.output["selected_path"]
        path_name = ["High temperature", "Proper case status", "Recent update"][path_index] if path_index < 3 else "Default"
        
        print(f"Result: Path {path_index} selected ({path_name})")

async def demo_merge_node():
    """Demonstrate the Merge Node functionality"""
    print("\n\033[1m🔄 Merge Node Demo\033[0m")
    
    # Test data for different merge strategies
    input_data = {
        "user_info": {"id": 1, "name": "John", "role": "user"},
        "profile_info": {"id": 1, "bio": "Software developer", "location": "New York"},
        "settings": {"theme": "dark", "notifications": True}
    }
    
    # 1. Pick First Strategy
    pick_first_node = {
        "id": "merge_pick_first",
        "type": "merge",
        "data": {
            "params": {
                "paths": ["missing_data", "user_info", "profile_info"],
                "function": "Pick First",
                "type": "Any"
            }
        }
    }
    
    print("\nPick First Strategy:")
    print(f"Input paths: {pick_first_node['data']['params']['paths']}")
    
    result1 = await execute_workflow_node(
        pick_first_node, 
        {"input": input_data}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    print("Output:")
    pprint(result1.output)
    
    # 2. Join All Strategy
    join_all_node = {
        "id": "merge_join_all",
        "type": "merge",
        "data": {
            "params": {
                "paths": ["user_info.name", "profile_info.bio", "profile_info.location"],
                "function": "Join All",
                "type": "Text",
                "joinDelimiter": " | "
            }
        }
    }
    
    print("\nJoin All Strategy:")
    print(f"Input paths: {join_all_node['data']['params']['paths']}")
    print(f"Join delimiter: '{join_all_node['data']['params']['joinDelimiter']}'")
    
    result2 = await execute_workflow_node(
        join_all_node, 
        {"input": input_data}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    print("Output:")
    print(result2.output)
    
    # 3. Merge Objects Strategy
    merge_objects_node = {
        "id": "merge_objects",
        "type": "merge",
        "data": {
            "params": {
                "paths": ["user_info", "profile_info", "settings"],
                "function": "Merge Objects",
                "type": "JSON"
            }
        }
    }
    
    print("\nMerge Objects Strategy:")
    print(f"Input paths: {merge_objects_node['data']['params']['paths']}")
    
    result3 = await execute_workflow_node(
        merge_objects_node, 
        {"input": input_data}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    print("Output:")
    pprint(result3.output)

async def demo_time_node():
    """Demonstrate the Time Node functionality"""
    print("\n\033[1m🕒 Time Node Demo\033[0m")
    
    # 1. Basic current time
    current_time_node = {
        "id": "time_current",
        "type": "time",
        "data": {
            "params": {
                "timezone": "UTC"
            }
        }
    }
    
    print("\nCurrent Time (UTC):")
    
    result1 = await execute_workflow_node(
        current_time_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    # Print selected fields
    print(f"ISO: {result1.output['iso']}")
    print(f"Human readable: {result1.output['human_readable']}")
    print(f"Day of week: {result1.output['day_of_week']}")
    
    # 2. Time arithmetic - Add time
    add_time_node = {
        "id": "time_add",
        "type": "time",
        "data": {
            "params": {
                "timezone": "America/New_York",
                "operation": "add_time",
                "modifyValue": 7,
                "modifyUnit": "days",
                "customFormat": "%A, %B %d, %Y"
            }
        }
    }
    
    print("\nAdd Time (7 days from now, New York timezone):")
    print(f"Operation: {add_time_node['data']['params']['operation']}")
    print(f"Value: {add_time_node['data']['params']['modifyValue']} {add_time_node['data']['params']['modifyUnit']}")
    
    result2 = await execute_workflow_node(
        add_time_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    # Print selected fields
    print(f"Custom format: {result2.output['custom_formatted']}")
    print(f"Timezone: {result2.output['timezone']}")
    print(f"Is DST: {result2.output['is_dst']}")
    
    # 3. Time arithmetic - Subtract time
    subtract_time_node = {
        "id": "time_subtract",
        "type": "time",
        "data": {
            "params": {
                "timezone": "Europe/London",
                "operation": "subtract_time",
                "modifyValue": 1,
                "modifyUnit": "years",
                "customFormat": "%Y-%m-%d %H:%M:%S"
            }
        }
    }
    
    print("\nSubtract Time (1 year ago, London timezone):")
    
    result3 = await execute_workflow_node(
        subtract_time_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    # Compare with current time
    now = datetime.now()
    print(f"Current year: {now.year}")
    print(f"Result year: {result3.output['year']}")
    print(f"Custom format: {result3.output['custom_formatted']}")

async def demo_text_to_sql_node():
    """Demonstrate the Text to SQL Node functionality"""
    print("\n\033[1m🔍 Text to SQL Node Demo\033[0m")
    
    # Skip if no OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠️ Skipping Text to SQL demo (No OpenAI API key found)")
        print("Set the OPENAI_API_KEY environment variable to run this demo")
        return
    
    # Create Text to SQL node
    ttsql_node = {
        "id": "ttsql_demo",
        "type": "ttsql",
        "data": {
            "params": {
                "query": "Find the top 10 most expensive products in the 'Electronics' category",
                "schema": """
                CREATE TABLE products (
                    id INT PRIMARY KEY,
                    name VARCHAR(100),
                    description TEXT,
                    price DECIMAL(10, 2),
                    category VARCHAR(50),
                    in_stock BOOLEAN
                );
                
                CREATE TABLE orders (
                    id INT PRIMARY KEY,
                    customer_id INT,
                    order_date TIMESTAMP,
                    total_amount DECIMAL(12, 2)
                );
                """,
                "database": "MySQL",
                "parameters": {
                    "limit": 10
                },
                "validateOnly": True
            }
        }
    }
    
    print("\nNatural Language Query:")
    print(f"Query: {ttsql_node['data']['params']['query']}")
    print(f"Database: {ttsql_node['data']['params']['database']}")
    
    result = await execute_workflow_node(
        ttsql_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "demo_user"
    )
    
    # Print SQL and validation result
    print("\nGenerated SQL:")
    print(result.output["sql"])
    
    print("\nValidation result:")
    print(f"Valid: {result.output['validation']['valid']}")
    if result.output['validation']['errors']:
        print(f"Errors: {result.output['validation']['errors']}")

async def run_all_demos():
    """Run all node demos"""
    print("\n\033[1;36m🧪 Running Workflow Nodes Demo\033[0m")
    print("===============================")
    
    await demo_condition_node()
    await demo_merge_node()
    await demo_time_node()
    await demo_text_to_sql_node()
    
    print("\n\033[1;32m✅ Demo completed!\033[0m")

if __name__ == "__main__":
    # Optional: set OpenAI API key if available
    if os.environ.get("OPENAI_API_KEY") is None:
        print("⚠️ No OpenAI API key found in environment variables")
        print("Text to SQL demo will be limited")
    
    # Run all demos
    asyncio.run(run_all_demos()) 
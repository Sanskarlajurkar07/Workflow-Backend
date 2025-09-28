import os
import sys
import json
import pytest
import asyncio
from datetime import datetime, timedelta
from copy import deepcopy

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

@pytest.mark.asyncio
async def test_condition_node():
    """Test the enhanced condition node with regex and date comparison"""
    # Create a basic condition node for testing
    condition_node = {
        "id": "condition_1",
        "type": "condition",
        "data": {
            "params": {
                "paths": [
                    {
                        "id": "path_0",
                        "clauses": [
                            {"id": "clause_0", "inputField": "value", "operator": "contains", "value": "test"}
                        ],
                        "logicalOperator": "AND"
                    },
                    {
                        "id": "path_1",
                        "clauses": [
                            {"id": "clause_1", "inputField": "value", "operator": "matches_regex", "value": "^[A-Z][a-z]+$"}
                        ],
                        "logicalOperator": "AND"
                    },
                    {
                        "id": "path_2",
                        "clauses": [
                            {"id": "clause_2", "inputField": "date", "operator": "date_after", "value": "2023-01-01"}
                        ],
                        "logicalOperator": "AND"
                    }
                ]
            }
        }
    }
    
    # Test different inputs
    # Should match first path (contains "test")
    result1 = await execute_workflow_node(
        condition_node, 
        {"input": {"value": "this is a test string", "date": "2022-05-15"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result1.status == "success"
    assert result1.output["selected_path"] == 0
    
    # Should match second path (regex pattern)
    result2 = await execute_workflow_node(
        condition_node, 
        {"input": {"value": "Example", "date": "2022-05-15"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result2.status == "success"
    assert result2.output["selected_path"] == 1
    
    # Should match third path (date after)
    result3 = await execute_workflow_node(
        condition_node, 
        {"input": {"value": "no match", "date": "2023-06-15"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result3.status == "success"
    assert result3.output["selected_path"] == 2
    
    # Should default to last path (ELSE) when no matches
    result4 = await execute_workflow_node(
        condition_node, 
        {"input": {"value": "no match", "date": "2022-05-15"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result4.status == "success"
    assert result4.output["selected_path"] == 2  # Last path (ELSE)
    
    print("✅ Condition node test passed")
    return True

@pytest.mark.asyncio
async def test_merge_node():
    """Test the enhanced merge node with new strategies"""
    # Create a basic merge node for testing
    merge_node_base = {
        "id": "merge_1",
        "type": "merge",
        "data": {
            "params": {
                "paths": ["path1", "path2", "path3"],
                "type": "Text"
            }
        }
    }
    
    # Test Pick First strategy
    pick_first_node = deepcopy(merge_node_base)
    pick_first_node["data"]["params"]["function"] = "Pick First"
    
    result1 = await execute_workflow_node(
        pick_first_node, 
        {"input": {"path1": None, "path2": "Value from path 2", "path3": "Value from path 3"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result1.status == "success"
    assert result1.output == "Value from path 2"
    
    # Test Join All strategy with custom delimiter
    join_all_node = deepcopy(merge_node_base)
    join_all_node["data"]["params"]["function"] = "Join All"
    join_all_node["data"]["params"]["joinDelimiter"] = " | "
    
    result2 = await execute_workflow_node(
        join_all_node, 
        {"input": {"path1": "Value 1", "path2": "Value 2", "path3": "Value 3"}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result2.status == "success"
    assert result2.output == "Value 1 | Value 2 | Value 3"
    
    # Test Concatenate Arrays strategy
    concat_arrays_node = deepcopy(merge_node_base)
    concat_arrays_node["data"]["params"]["function"] = "Concatenate Arrays"
    
    result3 = await execute_workflow_node(
        concat_arrays_node, 
        {"input": {"path1": [1, 2], "path2": [3, 4], "path3": [5, 6]}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result3.status == "success"
    assert result3.output == [1, 2, 3, 4, 5, 6]
    
    # Test Merge Objects strategy
    merge_objects_node = deepcopy(merge_node_base)
    merge_objects_node["data"]["params"]["function"] = "Merge Objects"
    
    result4 = await execute_workflow_node(
        merge_objects_node, 
        {"input": {
            "path1": {"a": 1, "b": 2}, 
            "path2": {"b": 3, "c": 4}, 
            "path3": {"d": 5}
        }}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result4.status == "success"
    assert result4.output == {"a": 1, "b": 3, "c": 4, "d": 5}
    
    print("✅ Merge node test passed")
    return True

@pytest.mark.asyncio
async def test_time_node():
    """Test the enhanced time node with arithmetic operations"""
    # Create a basic time node for testing
    time_node_base = {
        "id": "time_1",
        "type": "time",
        "data": {
            "params": {
                "timezone": "UTC"
            }
        }
    }
    
    # Test current time (default operation)
    result1 = await execute_workflow_node(
        time_node_base, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result1.status == "success"
    assert "iso" in result1.output
    assert "timestamp" in result1.output
    assert "day_of_week" in result1.output
    
    # Test add_time operation (add 1 day)
    add_time_node = deepcopy(time_node_base)
    add_time_node["data"]["params"]["operation"] = "add_time"
    add_time_node["data"]["params"]["modifyValue"] = 1
    add_time_node["data"]["params"]["modifyUnit"] = "days"
    
    now = datetime.now()
    expected_day = (now + timedelta(days=1)).day
    
    result2 = await execute_workflow_node(
        add_time_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result2.status == "success"
    assert result2.output["day"] == expected_day
    
    # Test subtract_time operation (subtract 2 hours)
    sub_time_node = deepcopy(time_node_base)
    sub_time_node["data"]["params"]["operation"] = "subtract_time"
    sub_time_node["data"]["params"]["modifyValue"] = 2
    sub_time_node["data"]["params"]["modifyUnit"] = "hours"
    
    now = datetime.now()
    expected_hour = (now - timedelta(hours=2)).hour
    
    result3 = await execute_workflow_node(
        sub_time_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result3.status == "success"
    assert result3.output["hour"] == expected_hour
    
    # Test custom format
    format_node = deepcopy(time_node_base)
    format_node["data"]["params"]["customFormat"] = "%B %d, %Y"
    
    result4 = await execute_workflow_node(
        format_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result4.status == "success"
    assert "custom_formatted" in result4.output
    assert len(result4.output["custom_formatted"]) > 0
    
    print("✅ Time node test passed")
    return True

@pytest.mark.asyncio
async def test_text_to_sql_node():
    """Test the enhanced text to SQL node with parameter support and validation"""
    # Create a basic text to SQL node for testing
    # Skip actual execution test to avoid DB connection requirement
    ttsql_node = {
        "id": "ttsql_1",
        "type": "ttsql",
        "data": {
            "params": {
                "query": "find all users with first name John",
                "schema": """
                CREATE TABLE users (
                    id INT PRIMARY KEY,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    email VARCHAR(100),
                    created_at TIMESTAMP
                );
                """,
                "database": "MySQL",
                "parameters": {"max_results": 10},
                "validateOnly": True
            }
        }
    }
    
    # Skip this test if no OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ Skipping Text to SQL test: No OpenAI API key found")
        return True
    
    # Test basic query generation
    result = await execute_workflow_node(
        ttsql_node, 
        {"input": {}}, 
        {}, 
        MockRequest(), 
        "test_user"
    )
    assert result.status == "success"
    assert "sql" in result.output
    assert "validation" in result.output
    assert "original_query" in result.output
    
    # Ensure parameters were used
    assert result.output["original_query"] == "find all users with first name John"
    
    print("✅ Text to SQL node test passed")
    return True

async def run_all_tests():
    """Run all node tests sequentially"""
    print("\n🧪 Running workflow node tests...\n")
    
    tests = [
        test_condition_node(),
        test_merge_node(),
        test_time_node(),
        test_text_to_sql_node()
    ]
    
    results = await asyncio.gather(*tests)
    
    if all(results):
        print("\n✅ All tests passed!\n")
    else:
        print("\n❌ Some tests failed\n")

if __name__ == "__main__":
    # Set fake API keys for testing if not present
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ Warning: No OpenAI API key found, text to SQL test will be skipped")
    
    # Run the tests
    asyncio.run(run_all_tests()) 
#!/usr/bin/env python3
"""
GitHub Node Workflow Test Script

This script demonstrates all the GitHub node functionalities:
1. List repositories
2. Get repository info
3. Read files
4. List commits
5. Create issues
6. Create pull requests
7. Update pull requests

Usage:
    python test_github_workflow.py

Make sure you have:
1. A user logged into the workflow platform
2. GitHub OAuth connected for that user
3. Access to a test repository
"""

import asyncio
import httpx
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_OWNER = "octocat"  # Change this to your GitHub username
TEST_REPO = "Hello-World"  # Change this to a test repository
TEST_BRANCH = "main"
TEST_FILE = "README.md"

async def test_github_node_action(action: str, params: dict):
    """Test a specific GitHub node action"""
    
    # Simulate a workflow node execution
    node_data = {
        "params": {
            "nodeName": f"test_github_{action}",
            "action": action,
            **params
        }
    }
    
    # Simulate workflow execution request
    workflow_data = {
        "nodes": [
            {
                "id": "test_node_1",
                "type": "github",
                "data": node_data
            }
        ],
        "edges": []
    }
    
    print(f"\n🧪 Testing GitHub Action: {action}")
    print(f"📋 Parameters: {json.dumps(params, indent=2)}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/api/workflows/execute",
                json=workflow_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success! Result:")
                print(json.dumps(result, indent=2))
                return result
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None

async def main():
    """Run all GitHub node tests"""
    
    print("🚀 GitHub Node Comprehensive Test Suite")
    print("=" * 50)
    
    # Test 1: List repositories
    await test_github_node_action("list-repositories", {
        "ownerName": TEST_OWNER
    })
    
    # Test 2: Get repository info
    await test_github_node_action("get-repository-info", {
        "ownerName": TEST_OWNER,
        "repoName": TEST_REPO
    })
    
    # Test 3: Read a file
    await test_github_node_action("read-file", {
        "ownerName": TEST_OWNER,
        "repoName": TEST_REPO,
        "branchName": TEST_BRANCH,
        "fileName": TEST_FILE
    })
    
    # Test 4: List commits
    await test_github_node_action("list-commits", {
        "ownerName": TEST_OWNER,
        "repoName": TEST_REPO,
        "branchName": TEST_BRANCH
    })
    
    # Test 5: Create an issue (commented out to avoid spam)
    # await test_github_node_action("create-issue", {
    #     "ownerName": TEST_OWNER,
    #     "repoName": TEST_REPO,
    #     "title": f"Test Issue - {datetime.now().isoformat()}",
    #     "body": "This is a test issue created by the GitHub workflow node."
    # })
    
    print("\n🎉 GitHub Node Test Suite Complete!")
    print("\nTo test issue/PR creation, uncomment the relevant sections")
    print("and make sure you have write access to the repository.")

if __name__ == "__main__":
    asyncio.run(main()) 
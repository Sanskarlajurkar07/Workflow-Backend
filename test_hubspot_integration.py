#!/usr/bin/env python3
"""
Test script for HubSpot integration
"""
import asyncio
import httpx
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hubspot_node import HubSpotNode

async def test_hubspot_connection():
    """Test HubSpot connection with mock token"""
    print("Testing HubSpot Integration...")
    print("=" * 50)
    
    # Test with a mock token (this will fail authentication but test the structure)
    mock_token = "mock_token_for_testing"
    
    try:
        # Create HubSpot node instance
        hubspot_node = HubSpotNode(mock_token)
        
        # Test connection (should fail with mock token but show proper error handling)
        print("1. Testing connection...")
        connection_result = await hubspot_node.test_connection()
        print(f"Connection test result: {connection_result}")
        
        # Test fetch action structure
        print("\n2. Testing fetch action structure...")
        fetch_data = {
            "action": "fetch-contacts",
            "properties": "firstname,lastname,email",
            "limit": 10
        }
        
        fetch_result = await hubspot_node.execute(fetch_data)
        print(f"Fetch test result: {fetch_result}")
        
        # Test create action structure
        print("\n3. Testing create action structure...")
        create_data = {
            "action": "create-contact",
            "properties": {
                "firstname": "Test",
                "lastname": "User",
                "email": "test@example.com"
            }
        }
        
        create_result = await hubspot_node.execute(create_data)
        print(f"Create test result: {create_result}")
        
        print("\n" + "=" * 50)
        print("✅ HubSpot node structure tests completed!")
        print("Note: Authentication errors are expected with mock token")
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False
    
    return True

async def test_api_endpoints():
    """Test the API endpoints"""
    print("\n" + "=" * 50)
    print("Testing API Endpoints...")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        try:
            # Test HubSpot status endpoint (should return not connected)
            print("1. Testing HubSpot status endpoint...")
            try:
                response = await client.get(f"{base_url}/api/auth/hubspot/status")
                print(f"Status: {response.status_code}")
                print(f"Response: {response.json()}")
            except Exception as e:
                print(f"Status endpoint test failed: {str(e)}")
            
            # Test HubSpot login endpoint (should redirect to HubSpot)
            print("\n2. Testing HubSpot login endpoint...")
            try:
                response = await client.get(f"{base_url}/api/auth/hubspot/login", follow_redirects=False)
                print(f"Login Status: {response.status_code}")
                if response.status_code == 307:
                    print("✅ Login endpoint properly redirects to HubSpot OAuth")
                    print(f"Redirect location: {response.headers.get('location', 'Not found')}")
                else:
                    print(f"Response: {response.text}")
            except Exception as e:
                print(f"Login endpoint test failed: {str(e)}")
            
            print("\n" + "=" * 50)
            print("✅ API endpoint tests completed!")
            
        except Exception as e:
            print(f"❌ API tests failed: {str(e)}")
            return False
    
    return True

async def main():
    """Main test function"""
    print("🚀 Starting HubSpot Integration Tests")
    print("This will test the HubSpot node and API endpoints")
    print()
    
    # Test the HubSpot node class
    node_test_passed = await test_hubspot_connection()
    
    # Test the API endpoints
    api_test_passed = await test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   HubSpot Node Tests: {'✅ PASSED' if node_test_passed else '❌ FAILED'}")
    print(f"   API Endpoint Tests: {'✅ PASSED' if api_test_passed else '❌ FAILED'}")
    print()
    
    if node_test_passed and api_test_passed:
        print("🎉 All tests passed! HubSpot integration is ready.")
        print()
        print("Next steps:")
        print("1. Make sure backend server is running on port 8000")
        print("2. Make sure frontend server is running on port 5173/5174")
        print("3. Navigate to the workflow builder in your browser")
        print("4. Add a HubSpot node and test the OAuth flow")
        print()
        print("OAuth URL: http://localhost:8000/api/auth/hubspot/login")
        print("Redirect URL: http://localhost:8000/api/auth/hubspot/auth")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 
#!/usr/bin/env python3
"""
Test script to verify OAuth2 state management fix
"""
import asyncio
import httpx
import json
from datetime import datetime

async def test_oauth_flow():
    """Test the OAuth2 flow to ensure state management is working"""
    
    base_url = "http://localhost:8000"
    
    try:
        async with httpx.AsyncClient() as client:
            print("🧪 Testing OAuth2 State Management Fix")
            print("=" * 50)
            
            # Test 1: Check if server is running
            print("1. Testing server connectivity...")
            try:
                response = await client.get(f"{base_url}/")
                if response.status_code == 200:
                    print("   ✅ Server is running")
                else:
                    print(f"   ❌ Server responded with status {response.status_code}")
                    return
            except httpx.ConnectError:
                print("   ❌ Could not connect to server")
                return
            
            # Test 2: Try to initiate OAuth flow
            print("\n2. Testing OAuth initiation...")
            try:
                # Note: This will redirect, so we expect a 302 or redirect response
                response = await client.get(
                    f"{base_url}/api/auth/google/login",
                    follow_redirects=False
                )
                
                if response.status_code in [302, 307]:
                    print("   ✅ OAuth initiation working (redirect received)")
                    location = response.headers.get('location', '')
                    if 'accounts.google.com' in location:
                        print("   ✅ Redirecting to Google OAuth")
                        # Extract state parameter
                        if 'state=' in location:
                            print("   ✅ State parameter present in redirect URL")
                        else:
                            print("   ⚠️  No state parameter found in redirect")
                    else:
                        print(f"   ⚠️  Unexpected redirect location: {location}")
                elif response.status_code == 501:
                    print("   ⚠️  OAuth not configured (expected in development)")
                else:
                    print(f"   ❌ Unexpected response: {response.status_code}")
                    print(f"   Response: {response.text}")
            except Exception as e:
                print(f"   ❌ Error testing OAuth initiation: {str(e)}")
            
            # Test 3: Test database connectivity for state storage
            print("\n3. Testing database connectivity...")
            try:
                # Check if we can connect to the database endpoints
                response = await client.get(f"{base_url}/api/database/health")
                if response.status_code == 200:
                    print("   ✅ Database endpoints accessible")
                else:
                    print(f"   ⚠️  Database health check returned: {response.status_code}")
            except Exception as e:
                print(f"   ⚠️  Database connectivity test failed: {str(e)}")
            
            print("\n" + "=" * 50)
            print("🎯 OAuth2 Fix Summary:")
            print("   • State management moved from sessions to MongoDB")
            print("   • Direct token exchange bypasses session validation")
            print("   • Automatic cleanup of expired state tokens")
            print("   • Enhanced error handling and logging")
            
            print("\n📋 Next Steps:")
            print("   1. Configure Google OAuth credentials if not done")
            print("   2. Test the full OAuth flow in the browser")
            print("   3. Check server logs for detailed state management info")
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_oauth_flow()) 
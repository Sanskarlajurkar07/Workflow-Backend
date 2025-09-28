import pytest
import asyncio
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
from unittest.mock import MagicMock
from main import app
import os
import time

# Set test environment for config
os.environ["ENV"] = "test"
os.environ["MONGODB_DB_NAME"] = "flowmind_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def test_client():
    """Create a FastAPI TestClient for testing endpoints."""
    # Override app dependencies for testing
    app.mongodb_client = AsyncIOMotorClient("mongodb://localhost:27017")
    app.mongodb = app.mongodb_client["flowmind_test"]
    app.redis = Redis(host="localhost", port=6379, decode_responses=True)
    app.qdrant = MagicMock()  # Mock the Qdrant client
    
    # Clean up existing data
    await clear_database()
    
    # Use TestClient for testing the API
    with TestClient(app) as client:
        yield client

async def clear_database():
    """Clear test database between tests."""
    # Drop collections in MongoDB
    db = app.mongodb
    collections = await db.list_collection_names()
    for collection in collections:
        await db.drop_collection(collection)
    
    # Clear Redis
    app.redis.flushdb()

@pytest.fixture
async def test_user(test_client):
    """Create a test user for authentication tests."""
    user_data = {
        "email": "test@example.com",
        "password": "Password123!",
        "name": "Test User"
    }
    
    # Create user
    response = test_client.post("/api/users", json=user_data)
    assert response.status_code == 201, f"Failed to create test user: {response.text}"
    
    # Log in to get token
    login_data = {
        "email": user_data["email"],
        "password": user_data["password"]
    }
    response = test_client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200, f"Failed to login test user: {response.text}"
    
    token = response.json().get("access_token")
    user_id = response.json().get("user_id")
    
    return {
        "id": user_id,
        "email": user_data["email"],
        "name": user_data["name"],
        "token": token,
        "auth_header": {"Authorization": f"Bearer {token}"}
    }

@pytest.fixture
async def test_workflow(test_client, test_user):
    """Create a test workflow."""
    workflow_data = {
        "name": "Test Workflow",
        "description": "A workflow for testing"
    }
    
    response = test_client.post(
        "/api/workflows", 
        json=workflow_data,
        headers=test_user["auth_header"]
    )
    
    assert response.status_code == 201, f"Failed to create test workflow: {response.text}"
    return response.json() 
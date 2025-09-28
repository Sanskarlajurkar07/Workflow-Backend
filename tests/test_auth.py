import pytest
from fastapi.testclient import TestClient

def test_login_with_valid_credentials(test_client: TestClient):
    """Test that a user can log in with valid credentials."""
    # Create a test user
    user_data = {
        "email": "logintest@example.com",
        "password": "Password123!",
        "name": "Login Test User"
    }
    
    response = test_client.post("/api/users", json=user_data)
    assert response.status_code == 201
    
    # Login with valid credentials
    login_data = {
        "email": user_data["email"],
        "password": user_data["password"]
    }
    
    response = test_client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert "user_id" in data
    assert "email" in data
    assert data["email"] == user_data["email"]

def test_login_with_invalid_credentials(test_client: TestClient):
    """Test that login fails with invalid credentials."""
    login_data = {
        "email": "doesnotexist@example.com",
        "password": "WrongPassword123!"
    }
    
    response = test_client.post("/api/auth/login", json=login_data)
    assert response.status_code == 401
    
    data = response.json()
    assert "detail" in data

def test_protected_route_without_token(test_client: TestClient):
    """Test that protected routes require authentication."""
    response = test_client.get("/api/users/me")
    assert response.status_code == 401
    
    data = response.json()
    assert "detail" in data

def test_protected_route_with_token(test_client: TestClient, test_user):
    """Test that protected routes work with authentication."""
    headers = test_user["auth_header"]
    
    response = test_client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert data["email"] == test_user["email"]

def test_logout(test_client: TestClient, test_user):
    """Test that a user can log out."""
    headers = test_user["auth_header"]
    
    # Verify authenticated
    response = test_client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    
    # Logout
    response = test_client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200
    
    # Verify can't access protected routes after logout
    response = test_client.get("/api/users/me", headers=headers)
    assert response.status_code == 401 
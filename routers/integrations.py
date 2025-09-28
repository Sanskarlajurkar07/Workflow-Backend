from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from models.user import User
from models.integrations import (
    IntegrationType, GitHubActionType, AirtableActionType, NotionActionType,
    IntegrationCredentials, GitHubCredentials, AirtableCredentials, NotionCredentials,
    GitHubIssueCreate, GitHubPRCreate, GitHubRepoInfo, GitHubIssueList,
    GitHubIssueGet, GitHubCommentCreate, AirtableListRecords, AirtableGetRecord,
    AirtableCreateRecord, AirtableUpdateRecord, AirtableDeleteRecord,
    NotionListDatabases, NotionQueryDatabase, NotionGetPage, NotionCreatePage,
    NotionUpdatePage, NotionCreateComment
)
from .auth import get_current_user
from typing import Dict, Any, List, Optional
import logging
import os
import time
import httpx
from config import settings
from bson import ObjectId
from datetime import datetime
# Removed import to fix circular dependency - these functions are now in routers/google_drive.py
from fastapi.responses import HTMLResponse
from database import get_database

# Initialize router
router = APIRouter()
logger = logging.getLogger("workflow_api")

# Environment variables for integration API keys (should be moved to .env file)
GITHUB_APP_CLIENT_ID = os.environ.get("GITHUB_APP_CLIENT_ID", "")
GITHUB_APP_CLIENT_SECRET = os.environ.get("GITHUB_APP_CLIENT_SECRET", "")

# Endpoints for managing integration credentials
@router.post("/credentials/{integration_type}", response_model=Dict[str, Any])
async def store_credentials(
    integration_type: IntegrationType,
    credentials: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Store integration credentials for a user"""
    try:
        # Validate credentials format based on integration type
        if integration_type == IntegrationType.GITHUB:
            GitHubCredentials(**credentials)
        elif integration_type == IntegrationType.AIRTABLE:
            AirtableCredentials(**credentials)
        elif integration_type == IntegrationType.NOTION:
            NotionCredentials(**credentials)
            
        # Store credentials in the database
        now = datetime.utcnow().isoformat()
        integration_doc = {
            "integration_type": integration_type,
            "user_id": str(current_user.id),
            "credentials": credentials,
            "created_at": now,
            "updated_at": now
        }
        
        # Check if credentials already exist
        existing = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": integration_type
        })
        
        if existing:
            # Update existing credentials
            await request.app.mongodb["integration_credentials"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"credentials": credentials, "updated_at": now}}
            )
            return {"status": "success", "message": f"{integration_type} credentials updated"}
        else:
            # Insert new credentials
            result = await request.app.mongodb["integration_credentials"].insert_one(integration_doc)
            return {"status": "success", "message": f"{integration_type} credentials stored", "id": str(result.inserted_id)}
            
    except Exception as e:
        logger.error(f"Error storing {integration_type} credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error storing credentials: {str(e)}"
        )

@router.get("/credentials/{integration_type}", response_model=Dict[str, Any])
async def get_credentials(
    integration_type: IntegrationType,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get integration credentials for a user"""
    try:
        # Fetch credentials from the database
        credentials = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": integration_type
        })
        
        if not credentials:
            return {"status": "not_found", "has_credentials": False}
            
        # Don't return the actual credentials, just confirm they exist
        return {
            "status": "success", 
            "has_credentials": True,
            "integration_type": integration_type,
            "created_at": credentials.get("created_at"),
            "updated_at": credentials.get("updated_at")
        }
            
    except Exception as e:
        logger.error(f"Error retrieving {integration_type} credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving credentials: {str(e)}"
        )

@router.delete("/credentials/{integration_type}", response_model=Dict[str, Any])
async def delete_credentials(
    integration_type: IntegrationType,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Delete integration credentials for a user"""
    try:
        # Delete credentials from the database
        result = await request.app.mongodb["integration_credentials"].delete_one({
            "user_id": str(current_user.id),
            "integration_type": integration_type
        })
        
        if result.deleted_count == 0:
            return {"status": "not_found", "message": f"No {integration_type} credentials found"}
            
        return {"status": "success", "message": f"{integration_type} credentials deleted"}
            
    except Exception as e:
        logger.error(f"Error deleting {integration_type} credentials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting credentials: {str(e)}"
        )

# GitHub Integration Endpoints
@router.post("/github/{action}", response_model=Dict[str, Any])
async def github_action(
    action: GitHubActionType,
    action_data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Execute GitHub API actions"""
    try:
        # Get GitHub credentials
        credentials = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.GITHUB
        })
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub credentials not found. Please connect your GitHub account first."
            )
            
        access_token = credentials["credentials"]["access_token"]
        
        # Execute the appropriate GitHub action
        if action == GitHubActionType.CREATE_ISSUE:
            return await github_create_issue(access_token, action_data)
        elif action == GitHubActionType.CREATE_PR:
            return await github_create_pr(access_token, action_data)
        elif action == GitHubActionType.GET_REPO_INFO:
            return await github_get_repo_info(access_token, action_data)
        elif action == GitHubActionType.LIST_ISSUES:
            return await github_list_issues(access_token, action_data)
        elif action == GitHubActionType.GET_ISSUE:
            return await github_get_issue(access_token, action_data)
        elif action == GitHubActionType.LIST_REPOS:
            return await github_list_repos(access_token)
        elif action == GitHubActionType.LIST_BRANCHES:
            return await github_list_branches(access_token, action_data)
        elif action == GitHubActionType.CREATE_COMMENT:
            return await github_create_comment(access_token, action_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported GitHub action: {action}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing GitHub action {action}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing GitHub action: {str(e)}"
        )

# Airtable Integration Endpoints
@router.post("/airtable/{action}", response_model=Dict[str, Any])
async def airtable_action(
    action: AirtableActionType,
    action_data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Execute Airtable API actions"""
    try:
        # Get Airtable credentials
        credentials = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.AIRTABLE
        })
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Airtable credentials not found. Please connect your Airtable account first."
            )
            
        api_key = credentials["credentials"]["api_key"]
        
        # Execute the appropriate Airtable action
        if action == AirtableActionType.LIST_RECORDS:
            return await airtable_list_records(api_key, action_data)
        elif action == AirtableActionType.GET_RECORD:
            return await airtable_get_record(api_key, action_data)
        elif action == AirtableActionType.CREATE_RECORD:
            return await airtable_create_record(api_key, action_data)
        elif action == AirtableActionType.UPDATE_RECORD:
            return await airtable_update_record(api_key, action_data)
        elif action == AirtableActionType.DELETE_RECORD:
            return await airtable_delete_record(api_key, action_data)
        elif action == AirtableActionType.LIST_BASES:
            return await airtable_list_bases(api_key)
        elif action == AirtableActionType.LIST_TABLES:
            return await airtable_list_tables(api_key, action_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported Airtable action: {action}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing Airtable action {action}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing Airtable action: {str(e)}"
        )

# Notion Integration Endpoints
@router.post("/notion/{action}", response_model=Dict[str, Any])
async def notion_action(
    action: NotionActionType,
    action_data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Execute Notion API actions"""
    try:
        # Get Notion credentials
        credentials = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": str(current_user.id),
            "integration_type": IntegrationType.NOTION
        })
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Notion credentials not found. Please connect your Notion account first."
            )
            
        access_token = credentials["credentials"]["access_token"]
        
        # Execute the appropriate Notion action
        if action == NotionActionType.LIST_DATABASES:
            return await notion_list_databases(access_token, action_data)
        elif action == NotionActionType.QUERY_DATABASE:
            return await notion_query_database(access_token, action_data)
        elif action == NotionActionType.GET_PAGE:
            return await notion_get_page(access_token, action_data)
        elif action == NotionActionType.CREATE_PAGE:
            return await notion_create_page(access_token, action_data)
        elif action == NotionActionType.UPDATE_PAGE:
            return await notion_update_page(access_token, action_data)
        elif action == NotionActionType.CREATE_COMMENT:
            return await notion_create_comment(access_token, action_data)
        elif action == NotionActionType.LIST_USERS:
            return await notion_list_users(access_token)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported Notion action: {action}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing Notion action {action}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error executing Notion action: {str(e)}"
        )

# Google Drive Integration Endpoints - these now redirect to the dedicated google_drive router
@router.post("/google-drive/auth-url", response_model=Dict[str, Any])
async def google_drive_auth_url(
    data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get Google Drive OAuth authentication URL - Redirects to the new endpoint"""
    try:
        # Redirect to the new endpoint in google_drive router
        from routers.google_drive import get_auth_url
        return await get_auth_url(data, request, current_user)
    
    except Exception as e:
        logger.error(f"Error getting Google Drive auth URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error initiating Google Drive authentication: {str(e)}"
        )

@router.post("/google-drive/complete-auth", response_model=Dict[str, Any])
async def google_drive_complete_auth(
    data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Complete Google Drive OAuth authentication flow - Redirects to the new endpoint"""
    try:
        # Redirect to the new endpoint in google_drive router
        from routers.google_drive import google_drive_complete_auth as complete_oauth
        return await complete_oauth(data, request, current_user)
    
    except Exception as e:
        logger.error(f"Error completing Google Drive auth: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error completing Google Drive authentication: {str(e)}"
        )

@router.get("/google-drive/auth-callback")
async def google_drive_auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Callback endpoint for Google Drive OAuth - Redirects to the new endpoint"""
    try:
        # Redirect to the new endpoint in google_drive router
        from routers.google_drive import oauth_callback
        return await oauth_callback(request, code, error, state)
    
    except Exception as e:
        logger.error(f"Error in Google Drive OAuth callback: {str(e)}", exc_info=True)
        return HTMLResponse(content=f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>")

# GitHub implementation functions
async def github_create_issue(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new issue in a GitHub repository"""
    payload = GitHubIssueCreate(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/issues",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={
                "title": payload.title,
                "body": payload.body,
                "labels": payload.labels if payload.labels else [],
                "assignees": payload.assignees if payload.assignees else []
            }
        )
        
        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_create_pr(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new pull request in a GitHub repository"""
    payload = GitHubPRCreate(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/pulls",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={
                "title": payload.title,
                "body": payload.body,
                "head": payload.head,
                "base": payload.base
            }
        )
        
        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_get_repo_info(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Get information about a GitHub repository"""
    payload = GitHubRepoInfo(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_list_issues(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """List issues in a GitHub repository"""
    payload = GitHubIssueList(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/issues",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"state": payload.state}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_get_issue(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific issue in a GitHub repository"""
    payload = GitHubIssueGet(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/issues/{payload.issue_number}",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_list_repos(access_token: str) -> Dict[str, Any]:
    """List repositories for the authenticated user"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"per_page": 100}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_list_branches(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """List branches in a GitHub repository"""
    payload = GitHubRepoInfo(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/branches",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def github_create_comment(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a comment on an issue in a GitHub repository"""
    payload = GitHubCommentCreate(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{payload.repo_owner}/{payload.repo_name}/issues/{payload.issue_number}/comments",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={"body": payload.body}
        )
        
        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

# Airtable implementation functions
async def airtable_list_records(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """List records in an Airtable table"""
    payload = AirtableListRecords(**data)
    
    params = {}
    if payload.max_records:
        params["maxRecords"] = payload.max_records
    if payload.view:
        params["view"] = payload.view
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.airtable.com/v0/{payload.base_id}/{payload.table_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_get_record(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific record from an Airtable table"""
    payload = AirtableGetRecord(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.airtable.com/v0/{payload.base_id}/{payload.table_id}/{payload.record_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_create_record(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new record in an Airtable table"""
    payload = AirtableCreateRecord(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.airtable.com/v0/{payload.base_id}/{payload.table_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"fields": payload.fields}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_update_record(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a record in an Airtable table"""
    payload = AirtableUpdateRecord(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"https://api.airtable.com/v0/{payload.base_id}/{payload.table_id}/{payload.record_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"fields": payload.fields}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_delete_record(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a record from an Airtable table"""
    payload = AirtableDeleteRecord(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.airtable.com/v0/{payload.base_id}/{payload.table_id}/{payload.record_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_list_bases(api_key: str) -> Dict[str, Any]:
    """List all bases for the authenticated Airtable user"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.airtable.com/v0/meta/bases",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def airtable_list_tables(api_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """List all tables in an Airtable base"""
    base_id = data.get("base_id")
    if not base_id:
        raise HTTPException(
            status_code=400,
            detail="base_id is required"
        )
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Airtable API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

# Notion implementation functions
async def notion_list_databases(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """List databases in Notion"""
    payload = NotionListDatabases(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            },
            json={
                "filter": {"property": "object", "value": "database"},
                "page_size": payload.page_size
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_query_database(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Query a Notion database"""
    payload = NotionQueryDatabase(**data)
    
    query_body = {}
    if payload.filter:
        query_body["filter"] = payload.filter
    if payload.sorts:
        query_body["sorts"] = payload.sorts
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.notion.com/v1/databases/{payload.database_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            },
            json=query_body
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_get_page(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a Notion page"""
    payload = NotionGetPage(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.notion.com/v1/pages/{payload.page_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_create_page(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new page in Notion"""
    payload = NotionCreatePage(**data)
    
    page_data = {
        "parent": {payload.parent_type: payload.parent_id},
        "properties": payload.properties
    }
    
    if payload.content:
        page_data["children"] = payload.content
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            },
            json=page_data
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_update_page(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a page in Notion"""
    payload = NotionUpdatePage(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"https://api.notion.com/v1/pages/{payload.page_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            },
            json={"properties": payload.properties}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_create_comment(access_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a comment on a Notion page or block"""
    payload = NotionCreateComment(**data)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.notion.com/v1/comments",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            },
            json={
                "parent": {payload.parent_type: payload.parent_id},
                "rich_text": [{"type": "text", "text": {"content": payload.comment_text}}]
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()}

async def notion_list_users(access_token: str) -> Dict[str, Any]:
    """List all users in a Notion workspace"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.notion.com/v1/users",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": "2022-06-28"
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Notion API error: {response.text}"
            )
            
        return {"status": "success", "data": response.json()} 
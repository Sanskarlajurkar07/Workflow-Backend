import logging
import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from models.workflow import NodeResult
import httpx
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

logger = logging.getLogger("workflow_api")

# Scopes for Google Drive API
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",                # Create, edit, and delete files created by the app
    "https://www.googleapis.com/auth/drive.metadata.readonly",   # View metadata for files
    "https://www.googleapis.com/auth/drive.readonly",            # View files and folders
]

async def handle_google_drive_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for the Google Drive node type"""
    logger.info(f"Executing Google Drive node {node_id}")
    
    # Extract parameters
    operation = node_data.get("params", {}).get("operation", "list_files")
    folder_id = node_data.get("params", {}).get("folderId", "root")
    file_id = node_data.get("params", {}).get("fileId", "")
    query = node_data.get("params", {}).get("query", "")
    file_path = node_data.get("params", {}).get("filePath", "")
    file_name = node_data.get("params", {}).get("fileName", "")
    file_mime_type = node_data.get("params", {}).get("fileMimeType", "")
    page_size = node_data.get("params", {}).get("pageSize", 10)
    auth_token = node_data.get("params", {}).get("authToken", None)
    refresh_token = node_data.get("params", {}).get("refreshToken", None)
    client_id = node_data.get("params", {}).get("clientId", None)
    client_secret = node_data.get("params", {}).get("clientSecret", None)
    node_name = node_data.get("params", {}).get("nodeName", f"google_drive_{node_id[:4]}")
    
    # Check for auth tokens from previous connections
    if not auth_token and not refresh_token:
        # Look for auth tokens in the inputs
        for key, value in inputs.items():
            if isinstance(value, dict) and "access_token" in value and "refresh_token" in value:
                auth_token = value.get("access_token")
                refresh_token = value.get("refresh_token")
                client_id = value.get("client_id", client_id)
                client_secret = value.get("client_secret", client_secret)
                break

    try:
        # Build credentials
        if auth_token and refresh_token and client_id and client_secret:
            credentials = Credentials(
                token=auth_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            # Check if credentials need refreshing
            if credentials.expired:
                logger.info("Refreshing Google Drive credentials")
                credentials.refresh(Request())
                
                # Update token info in node_data for next time
                node_data["params"]["authToken"] = credentials.token
                node_data["params"]["refreshToken"] = credentials.refresh_token
        else:
            # No authentication provided
            return NodeResult(
                output={"error": "Authentication failed. Please connect to Google Drive using OAuth."},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error="Authentication required",
                node_id=node_id,
                node_name=node_name
            )
        
        # Build Drive service
        drive_service = build('drive', 'v3', credentials=credentials)
        
        result = {}
        
        # Execute operation
        if operation == "list_files":
            result = await list_files(drive_service, folder_id, query, page_size)
        elif operation == "get_file":
            result = await get_file(drive_service, file_id)
        elif operation == "upload_file":
            result = await upload_file(drive_service, file_path, file_name, file_mime_type, folder_id)
        elif operation == "create_folder":
            result = await create_folder(drive_service, file_name, folder_id)
        elif operation == "delete_file":
            result = await delete_file(drive_service, file_id)
        elif operation == "search_files":
            result = await search_files(drive_service, query, page_size)
        else:
            return NodeResult(
                output={"error": f"Unsupported operation: {operation}"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Unsupported operation: {operation}",
                node_id=node_id,
                node_name=node_name
            )
        
        # Add authentication info to the result
        result["auth_info"] = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "token_uri": credentials.token_uri,
            "scopes": credentials.scopes,
        }
        
        # Store result in workflow data
        workflow_data[node_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_name
        )
        
    except RefreshError as e:
        logger.error(f"Google Drive token refresh error: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": "Authentication token expired. Please reconnect to Google Drive."},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="Authentication token expired",
            node_id=node_id,
            node_name=node_name
        )
    except Exception as e:
        logger.error(f"Error in Google Drive node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        )

async def list_files(drive_service, folder_id="root", query="", page_size=10):
    """List files in a Google Drive folder"""
    # Build the query
    if query:
        if folder_id and folder_id != "root":
            query = f"'{folder_id}' in parents and ({query})"
        # If no folder_id specified, just use the query as is
    else:
        if folder_id and folder_id != "root":
            query = f"'{folder_id}' in parents"
        # If no folder_id and no query, list all files accessible to the app
    
    # Call the Drive API
    results = drive_service.files().list(
        q=query if query else None,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)"
    ).execute()
    
    files = results.get('files', [])
    next_page_token = results.get('nextPageToken', None)
    
    return {
        "files": files,
        "next_page_token": next_page_token,
        "count": len(files)
    }

async def get_file(drive_service, file_id):
    """Get metadata for a specific file"""
    file = drive_service.files().get(
        fileId=file_id,
        fields="id, name, mimeType, size, modifiedTime, webViewLink, parents"
    ).execute()
    
    return {
        "file": file
    }

async def upload_file(drive_service, file_path, file_name="", file_mime_type="", folder_id="root"):
    """Upload a file to Google Drive"""
    if not file_name:
        file_name = os.path.basename(file_path)
    
    # Auto-detect mime type if not provided
    if not file_mime_type:
        from mimetypes import guess_type
        file_mime_type = guess_type(file_path)[0]
        if not file_mime_type:
            file_mime_type = 'application/octet-stream'
    
    file_metadata = {
        'name': file_name
    }
    
    if folder_id and folder_id != "root":
        file_metadata['parents'] = [folder_id]
    
    media = MediaFileUpload(file_path, mimetype=file_mime_type)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, mimeType, size, webViewLink'
    ).execute()
    
    return {
        "file": file
    }

async def create_folder(drive_service, folder_name, parent_folder_id="root"):
    """Create a folder in Google Drive"""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    if parent_folder_id and parent_folder_id != "root":
        file_metadata['parents'] = [parent_folder_id]
    
    folder = drive_service.files().create(
        body=file_metadata,
        fields='id, name, mimeType, webViewLink'
    ).execute()
    
    return {
        "folder": folder
    }

async def delete_file(drive_service, file_id):
    """Delete a file from Google Drive"""
    drive_service.files().delete(fileId=file_id).execute()
    
    return {
        "success": True,
        "message": f"File with ID {file_id} deleted successfully"
    }

async def search_files(drive_service, query, page_size=10):
    """Search for files in Google Drive"""
    results = drive_service.files().list(
        q=query,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)"
    ).execute()
    
    files = results.get('files', [])
    next_page_token = results.get('nextPageToken', None)
    
    return {
        "files": files,
        "next_page_token": next_page_token,
        "count": len(files)
    }

async def init_google_drive_oauth(client_id, client_secret, redirect_uri):
    """Initialize OAuth flow for Google Drive"""
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )
    
    # Get the authorization URL
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return {
        "auth_url": auth_url
    }

async def complete_google_drive_oauth(client_id, client_secret, redirect_uri, code):
    """Complete OAuth flow for Google Drive with authorization code"""
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )
    
    # Exchange authorization code for access token
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    } 
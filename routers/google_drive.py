from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from typing import Dict, Any, Optional
import logging
import os
import httpx
import json
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from models.oauth_connections import (
    OAuthConnectionCreate,
    OAuthConnectionUpdate,
    get_oauth_connection,
    create_oauth_connection,
    update_oauth_connection,
    deactivate_oauth_connection,
    list_user_connections
)
from database import get_database
from auth.auth_handler import get_current_user
from models.user import User

# Configure OAuth client
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

router = APIRouter(
    prefix="/api/google-drive",
    tags=["google-drive"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger("workflow_api")

# Helper function to create OAuth flow
def create_oauth_flow(client_id: str, client_secret: str, redirect_uri: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = redirect_uri
    return flow

@router.post("/auth-url")
async def get_auth_url(
    data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get Google Drive OAuth2 authorization URL"""
    try:
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        redirect_uri = data.get("redirect_uri", str(request.url_for("oauth_callback")))
        
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client ID and Client Secret are required"
            )
        
        # Create OAuth flow
        flow = create_oauth_flow(client_id, client_secret, redirect_uri)
        
        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        
        # Store client info in session for callback
        request.session["oauth_state"] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "user_id": str(current_user.id)
        }
        
        return {"auth_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error generating Google Drive auth URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )

@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = None,
    error: str = None,
    db = Depends(get_database)
):
    """Handle OAuth callback from Google"""
    if error:
        return JSONResponse(
            content={"error": error, "success": False},
            status_code=400
        )
    
    if not code:
        return JSONResponse(
            content={"error": "No authorization code received", "success": False},
            status_code=400
        )
    
    try:
        # Get session data
        oauth_state = request.session.get("oauth_state")
        if not oauth_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="OAuth session expired. Please try again."
            )
        
        client_id = oauth_state.get("client_id")
        client_secret = oauth_state.get("client_secret")
        redirect_uri = oauth_state.get("redirect_uri")
        user_id = oauth_state.get("user_id")
        
        # Create OAuth flow and exchange code for tokens
        flow = create_oauth_flow(client_id, client_secret, redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Store tokens in database
        expiry = credentials.expiry if credentials.expiry else datetime.utcnow() + timedelta(seconds=3600)
        
        connection_data = OAuthConnectionCreate(
            user_id=user_id,
            service_name="google_drive",
            client_id=client_id,
            client_secret=client_secret,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=expiry,
            scope=credentials.scopes[0] if credentials.scopes else SCOPES[0],
            token_type=credentials.token_type,
            additional_data={}
        )
        
        await create_oauth_connection(db, connection_data)
        
        # Clear session data
        if "oauth_state" in request.session:
            del request.session["oauth_state"]
        
        # Create HTML page that will send a message to the opener window and close itself
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <script>
                window.onload = function() {{
                    window.opener.postMessage({{
                        type: 'google_drive_auth',
                        success: true,
                        code: '{code}'
                    }}, '*');
                    setTimeout(function() {{ window.close(); }}, 1000);
                }};
            </script>
        </head>
        <body>
            <h1>Authentication Successful!</h1>
            <p>You can close this window and return to the application.</p>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.error(f"Error in Google Drive OAuth callback: {str(e)}")
        return JSONResponse(
            content={"error": str(e), "success": False},
            status_code=500
        )

@router.get("/connections")
async def get_user_connections(
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get all Google Drive connections for the current user"""
    try:
        connections = await list_user_connections(db, str(current_user.id))
        
        # Filter to only Google Drive connections
        google_drive_connections = [
            {
                "id": str(conn["_id"]),
                "client_id": conn["client_id"],
                "service_name": conn["service_name"],
                "created_at": conn["created_at"],
                "updated_at": conn["updated_at"],
                "is_active": conn["is_active"],
                "token_expiry": conn.get("token_expiry")
            }
            for conn in connections
            if conn["service_name"] == "google_drive"
        ]
        
        return {"connections": google_drive_connections}
    
    except Exception as e:
        logger.error(f"Error fetching Google Drive connections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch connections: {str(e)}"
        )

@router.post("/disconnect")
async def disconnect_google_drive(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
):
    """Disconnect Google Drive integration"""
    try:
        connection_id = data.get("connection_id")
        
        if connection_id:
            # Deactivate specific connection
            await update_oauth_connection(
                db, 
                connection_id, 
                OAuthConnectionUpdate(is_active=False)
            )
        else:
            # Deactivate all Google Drive connections for this user
            await deactivate_oauth_connection(db, str(current_user.id), "google_drive")
        
        return {"message": "Google Drive disconnected successfully", "success": True}
    
    except Exception as e:
        logger.error(f"Error disconnecting Google Drive: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect Google Drive: {str(e)}"
        )

@router.post("/refresh-token")
async def refresh_access_token(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
):
    """Refresh the access token for Google Drive"""
    try:
        connection_id = data.get("connection_id")
        
        if not connection_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connection ID is required"
            )
        
        # Get connection from database
        connection = await db.oauth_connections.find_one({"_id": ObjectId(connection_id)})
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Check if user owns this connection
        if connection["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this connection"
            )
        
        # Create credentials object
        creds = Credentials(
            token=connection["access_token"],
            refresh_token=connection["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=connection["client_id"],
            client_secret=connection["client_secret"],
            scopes=[connection.get("scope", SCOPES[0])]
        )
        
        # Refresh token if expired
        if creds.expired:
            creds.refresh(GoogleRequest())
            
            # Update connection in database
            await update_oauth_connection(
                db,
                connection_id,
                OAuthConnectionUpdate(
                    access_token=creds.token,
                    token_expiry=creds.expiry,
                    token_type=creds.token_type
                )
            )
        
        return {
            "access_token": creds.token,
            "token_expiry": creds.expiry,
            "success": True
        }
    
    except Exception as e:
        logger.error(f"Error refreshing Google Drive token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        ) 
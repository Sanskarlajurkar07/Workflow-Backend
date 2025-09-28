from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from config import settings
from models.user import User
from routers.auth import get_current_user
from database import get_user_collection
import httpx
import secrets
import logging
from typing import Optional, Dict
from datetime import datetime
import json

logger = logging.getLogger("workflow_api")

router = APIRouter()

# Google OAuth configuration for workflow nodes
GOOGLE_NODE_CLIENT_ID = "168656444308-5049dq3j9b326q5lrf7828eaolv703t9.apps.googleusercontent.com"
GOOGLE_NODE_CLIENT_SECRET = "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"

# OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for different Google services
GOOGLE_SCOPES = {
    "googledrive": [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.readonly"
    ],
    "googledocs": [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file"
    ],
    "googlesheet": [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file"
    ],
    "googlecalendar": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly"
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify"
    ]
}

@router.get("/auth/{service}/login")
async def google_service_login(
    request: Request,
    service: str,
    current_user: User = Depends(get_current_user)
):
    """Initiate OAuth flow for a specific Google service"""
    if service not in GOOGLE_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}"
        )
    
    # Generate state parameter for security
    state = secrets.token_urlsafe(32)
    
    # Store state in session
    request.session[f"google_{service}_state"] = state
    request.session[f"google_{service}_user_id"] = current_user.id
    
    # Get the appropriate scopes for the service
    scopes = GOOGLE_SCOPES[service]
    scope_string = " ".join(scopes)
    
    # Build redirect URI
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/{service}/callback"
    
    # Build authorization URL
    auth_params = {
        "client_id": GOOGLE_NODE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope_string,
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    
    auth_url = f"{GOOGLE_AUTH_URL}?" + "&".join([f"{k}={v}" for k, v in auth_params.items()])
    
    logger.info(f"Initiating Google OAuth for service: {service}, user: {current_user.id}")
    
    return RedirectResponse(url=auth_url, status_code=302)

@router.get("/auth/{service}/callback")
async def google_service_callback(
    request: Request,
    service: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """Handle OAuth callback for Google services"""
    if service not in GOOGLE_SCOPES:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/workflows?error=invalid_service",
            status_code=302
        )
    
    if error:
        logger.error(f"Google OAuth error for {service}: {error}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/workflows?error={error}",
            status_code=302
        )
    
    # Verify state parameter
    stored_state = request.session.get(f"google_{service}_state")
    if not state or state != stored_state:
        logger.error(f"Invalid state parameter for {service}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/workflows?error=invalid_state",
            status_code=302
        )
    
    # Get user ID from session
    user_id = request.session.get(f"google_{service}_user_id")
    if not user_id:
        logger.error(f"No user ID in session for {service}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/workflows?error=no_user",
            status_code=302
        )
    
    try:
        # Exchange code for tokens
        redirect_uri = f"{settings.BACKEND_URL}/api/auth/{service}/callback"
        
        token_data = {
            "code": code,
            "client_id": GOOGLE_NODE_CLIENT_ID,
            "client_secret": GOOGLE_NODE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(GOOGLE_TOKEN_URL, data=token_data)
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed for {service}: {token_response.text}")
                raise HTTPException(
                    status_code=token_response.status_code,
                    detail="Failed to exchange authorization code"
                )
            
            tokens = token_response.json()
            
            # Get user info (optional, for verification)
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            userinfo_response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
            
            if userinfo_response.status_code == 200:
                userinfo = userinfo_response.json()
                logger.info(f"Google {service} authenticated for user: {userinfo.get('email')}")
            
            # Store tokens in database
            user_collection = await get_user_collection(request)
            
            # Update user's Google credentials for this service
            update_data = {
                f"google_{service}_tokens": {
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "token_type": tokens.get("token_type", "Bearer"),
                    "expires_in": tokens.get("expires_in"),
                    "scope": tokens.get("scope"),
                    "authenticated_at": datetime.utcnow().isoformat(),
                    "email": userinfo.get("email") if userinfo_response.status_code == 200 else None
                }
            }
            
            await user_collection.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
            
            # Clear session data
            request.session.pop(f"google_{service}_state", None)
            request.session.pop(f"google_{service}_user_id", None)
            
            # Redirect back to frontend with success
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/workflows?google_{service}_connected=true",
                status_code=302
            )
            
    except Exception as e:
        logger.error(f"Error during Google {service} callback: {str(e)}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/workflows?error=authentication_failed",
            status_code=302
        )

@router.get("/auth/{service}/status")
async def google_service_status(
    request: Request,
    service: str,
    current_user: User = Depends(get_current_user)
):
    """Check if user has valid Google tokens for a service"""
    if service not in GOOGLE_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}"
        )
    
    user_collection = await get_user_collection(request)
    user = await user_collection.find_one({"_id": current_user.id})
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    service_tokens = user.get(f"google_{service}_tokens")
    
    if not service_tokens:
        return JSONResponse({
            "connected": False,
            "service": service
        })
    
    # Check if we have required tokens
    has_tokens = bool(
        service_tokens.get("access_token") and 
        service_tokens.get("refresh_token")
    )
    
    return JSONResponse({
        "connected": has_tokens,
        "service": service,
        "email": service_tokens.get("email"),
        "authenticated_at": service_tokens.get("authenticated_at")
    })

@router.post("/auth/{service}/refresh")
async def refresh_google_token(
    request: Request,
    service: str,
    current_user: User = Depends(get_current_user)
):
    """Refresh Google access token for a service"""
    if service not in GOOGLE_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}"
        )
    
    user_collection = await get_user_collection(request)
    user = await user_collection.find_one({"_id": current_user.id})
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    service_tokens = user.get(f"google_{service}_tokens")
    
    if not service_tokens or not service_tokens.get("refresh_token"):
        raise HTTPException(
            status_code=400,
            detail=f"No refresh token found for {service}"
        )
    
    try:
        # Refresh the access token
        refresh_data = {
            "refresh_token": service_tokens["refresh_token"],
            "client_id": GOOGLE_NODE_CLIENT_ID,
            "client_secret": GOOGLE_NODE_CLIENT_SECRET,
            "grant_type": "refresh_token"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=refresh_data)
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed for {service}: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to refresh token"
                )
            
            new_tokens = response.json()
            
            # Update stored tokens
            service_tokens["access_token"] = new_tokens.get("access_token")
            service_tokens["expires_in"] = new_tokens.get("expires_in")
            service_tokens["refreshed_at"] = datetime.utcnow().isoformat()
            
            await user_collection.update_one(
                {"_id": current_user.id},
                {"$set": {f"google_{service}_tokens": service_tokens}}
            )
            
            return JSONResponse({
                "success": True,
                "access_token": new_tokens.get("access_token"),
                "expires_in": new_tokens.get("expires_in")
            })
            
    except Exception as e:
        logger.error(f"Error refreshing Google {service} token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh token"
        )

@router.post("/auth/{service}/disconnect")
async def disconnect_google_service(
    request: Request,
    service: str,
    current_user: User = Depends(get_current_user)
):
    """Disconnect a Google service by removing stored tokens"""
    if service not in GOOGLE_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}"
        )
    
    user_collection = await get_user_collection(request)
    
    # Remove the service tokens
    await user_collection.update_one(
        {"_id": current_user.id},
        {"$unset": {f"google_{service}_tokens": ""}}
    )
    
    logger.info(f"Disconnected Google {service} for user: {current_user.id}")
    
    return JSONResponse({
        "success": True,
        "message": f"Google {service} disconnected successfully"
    }) 

@router.post("/auth/google/callback")
async def google_oauth_callback(request: Request):
    """Handle Google OAuth2 callback and token exchange"""
    try:
        data = await request.json()
        code = data.get("code")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        redirect_uri = data.get("redirect_uri")

        if not all([code, client_id, client_secret, redirect_uri]):
            raise HTTPException(status_code=400, detail="Missing required parameters")

        # Exchange authorization code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )

            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Google token exchange failed: {error_message}")
                
                if 'access_denied' in error_message:
                    error_message = 'This app is in testing mode. Please make sure your Google account is added as a test user.'
                elif 'invalid_client' in error_message:
                    error_message = 'Invalid client configuration. Please check your Google Cloud Console settings.'
                
                raise HTTPException(
                    status_code=token_response.status_code,
                    detail=error_message
                )

            tokens = token_response.json()
            
            return JSONResponse(content={
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "expires_in": tokens.get("expires_in"),
                "token_type": tokens.get("token_type")
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/googledocs/callback")
async def google_docs_callback(request: Request, code: str, state: str):
    """Handle Google Docs OAuth2 callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_NODE_CLIENT_ID,
                    "client_secret": GOOGLE_NODE_CLIENT_SECRET,
                    "redirect_uri": "http://localhost:8000/api/auth/googledocs/callback",
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Google Docs token exchange failed: {error_message}")
                
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/oauth/callback/googledocs?error={error_message}"
                )
                
            tokens = token_response.json()
            
            # Redirect to frontend OAuth callback page with tokens
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/oauth/callback/googledocs?success=true&access_token={tokens['access_token']}&refresh_token={tokens.get('refresh_token', '')}&workflow=true"
            )
            
    except Exception as e:
        logger.error(f"Error in Google Docs callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/googledocs?error={str(e)}"
        )

@router.get("/auth/googledrive/callback")
async def google_drive_callback(request: Request, code: str, state: str):
    """Handle Google Drive OAuth2 callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_NODE_CLIENT_ID,
                    "client_secret": GOOGLE_NODE_CLIENT_SECRET,
                    "redirect_uri": "http://localhost:8000/api/auth/googledrive/callback",
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Google Drive token exchange failed: {error_message}")
                
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/oauth/callback/googledrive?error={error_message}"
                )
                
            tokens = token_response.json()
            
            # Redirect to frontend OAuth callback page with tokens
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/oauth/callback/googledrive?success=true&access_token={tokens['access_token']}&refresh_token={tokens.get('refresh_token', '')}&workflow=true"
            )
            
    except Exception as e:
        logger.error(f"Error in Google Drive callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/googledrive?error={str(e)}"
        )

@router.get("/auth/gmail/callback")
async def gmail_callback(request: Request, code: str, state: str):
    """Handle Gmail OAuth2 callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_NODE_CLIENT_ID,
                    "client_secret": GOOGLE_NODE_CLIENT_SECRET,
                    "redirect_uri": "http://localhost:8000/api/auth/gmail/callback",
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Gmail token exchange failed: {error_message}")
                
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/oauth/callback/gmail?error={error_message}"
                )
                
            tokens = token_response.json()
            
            # Redirect to frontend OAuth callback page with tokens
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/oauth/callback/gmail?success=true&access_token={tokens['access_token']}&refresh_token={tokens.get('refresh_token', '')}&workflow=true"
            )
            
    except Exception as e:
        logger.error(f"Error in Gmail callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/gmail?error={str(e)}"
        )

@router.get("/auth/googlesheet/callback")
async def google_sheet_callback(request: Request, code: str, state: str):
    """Handle Google Sheets OAuth2 callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_NODE_CLIENT_ID,
                    "client_secret": GOOGLE_NODE_CLIENT_SECRET,
                    "redirect_uri": "http://localhost:8000/api/auth/googlesheet/callback",
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Google Sheets token exchange failed: {error_message}")
                
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/oauth/callback/googlesheet?error={error_message}"
                )
                
            tokens = token_response.json()
            
            # Redirect to frontend OAuth callback page with tokens
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/oauth/callback/googlesheet?success=true&access_token={tokens['access_token']}&refresh_token={tokens.get('refresh_token', '')}&workflow=true"
            )
            
    except Exception as e:
        logger.error(f"Error in Google Sheets callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/googlesheet?error={str(e)}"
        )

@router.get("/auth/googlecalendar/callback")
async def google_calendar_callback(request: Request, code: str, state: str):
    """Handle Google Calendar OAuth2 callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_NODE_CLIENT_ID,
                    "client_secret": GOOGLE_NODE_CLIENT_SECRET,
                    "redirect_uri": "http://localhost:8000/api/auth/googlecalendar/callback",
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json()
                error_message = error_data.get('error_description') or error_data.get('error', 'Failed to exchange code for tokens')
                logger.error(f"Google Calendar token exchange failed: {error_message}")
                
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/oauth/callback/googlecalendar?error={error_message}"
                )
                
            tokens = token_response.json()
            
            # Redirect to frontend OAuth callback page with tokens
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/oauth/callback/googlecalendar?success=true&access_token={tokens['access_token']}&refresh_token={tokens.get('refresh_token', '')}&workflow=true"
            )
            
    except Exception as e:
        logger.error(f"Error in Google Calendar callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/googlecalendar?error={str(e)}"
        ) 
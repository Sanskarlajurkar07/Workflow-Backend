from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from typing import Optional
import httpx
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])

# Slack API Configuration
SLACK_CLIENT_ID = "8803196426178.8946644524070"
SLACK_CLIENT_SECRET = "48bc071ec2284bfa3f753b5ea3b70194"
SLACK_SIGNING_SECRET = "32409b58869324f982aa32c5ace42e80"
SLACK_REDIRECT_URI = "http://localhost:8000/api/slack/oauth/callback"  # Force HTTP for local development

@router.get("/oauth/callback")
async def slack_oauth_callback(code: str, state: Optional[str] = None):
    """Handle the Slack OAuth callback"""
    try:
        logger.info("Received Slack OAuth callback")
        
        async with httpx.AsyncClient() as client:
            # Exchange the temporary code for an access token
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": SLACK_CLIENT_ID,
                    "client_secret": SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": SLACK_REDIRECT_URI
                },
            )
            
            data = response.json()
            logger.debug(f"Slack OAuth response: {data}")
            
            if not data.get("ok"):
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Slack OAuth error: {error_msg}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "type": "SLACK_OAUTH_ERROR",
                        "error": f"Slack OAuth error: {error_msg}"
                    }
                )
            
            # Return success response with access token
            return {
                "type": "SLACK_OAUTH_SUCCESS",
                "access_token": data["access_token"],
                "team_id": data.get("team", {}).get("id"),
                "team_name": data.get("team", {}).get("name")
            }
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "type": "SLACK_OAUTH_ERROR",
                "error": str(e)
            }
        )

@router.get("/channels")
async def get_slack_channels(authorization: str = Header(...)):
    """Get list of channels for the authenticated user"""
    try:
        token = authorization.replace("Bearer ", "")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/conversations.list",
                headers={
                    "Authorization": f"Bearer {token}"
                },
                params={
                    "types": "public_channel,private_channel",
                    "exclude_archived": True
                }
            )
            
            data = response.json()
            
            if not data.get("ok"):
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Slack channels error: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Slack API error: {error_msg}"
                )
            
            channels = [
                {"id": channel["id"], "name": channel["name"]}
                for channel in data.get("channels", [])
            ]
            
            return {"channels": channels}
    except Exception as e:
        logger.error(f"Error fetching Slack channels: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 
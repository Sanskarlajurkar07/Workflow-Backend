from fastapi import APIRouter, Depends, HTTPException, status, Request
from models.user import User, UserUpdate
from database import get_user_collection
from .auth import get_current_user_optional_token
from bson import ObjectId
from typing import Dict, Any, List, Optional
from models.integrations import IntegrationType

router = APIRouter()

@router.get("/me", response_model=User)
async def read_users_me(request: Request, current_user: User = Depends(get_current_user_optional_token)):
    # We already have the current user from the dependency
    return current_user

@router.put("/me", response_model=User)
async def update_user(
    user_update: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    user_collection = await get_user_collection(request)
    user = await user_collection.find_one_and_update(
        {"_id": ObjectId(current_user.id)},
        {"$set": user_update.dict(exclude_unset=True)},
        return_document=True
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user, id=str(user["_id"]))

@router.get("/me/integrations", response_model=Dict[str, Any])
async def get_user_integrations(
    request: Request,
    current_user: User = Depends(get_current_user_optional_token)
):
    """Get all integration connections for the current user"""
    try:
        # Query integration credentials collection
        credentials = await request.app.mongodb["integration_credentials"].find({
            "user_id": str(current_user.id)
        }).to_list(None)
        
        # Format the response
        integrations = {}
        for cred in credentials:
            integration_type = cred.get("integration_type")
            if integration_type:
                integrations[integration_type] = {
                    "connected": True,
                    "created_at": cred.get("created_at"),
                    "updated_at": cred.get("updated_at")
                }
                
        # Add missing integrations as not connected
        for integration in [t.value for t in IntegrationType]:
            if integration not in integrations:
                integrations[integration] = {
                    "connected": False
                }
                
        return {
            "integrations": integrations
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user integrations: {str(e)}"
        )
from datetime import datetime
from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, Dict, Any, List, Annotated
from bson import ObjectId
from pymongo import ReturnDocument

# Simple function to convert strings to ObjectIds
def parse_object_id(value):
    if isinstance(value, str):
        return ObjectId(value)
    return value

# Use Annotated for proper ObjectId handling
PyObjectId = Annotated[ObjectId, BeforeValidator(parse_object_id)]

class OAuthConnection(BaseModel):
    """Model for OAuth connection details"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    service_name: str  # e.g., "google_drive", "gmail", "outlook"
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scope: Optional[str] = None
    token_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    additional_data: Optional[Dict[str, Any]] = None
    is_active: bool = True

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "user_id": "user123",
                "service_name": "google_drive",
                "client_id": "your-client-id.apps.googleusercontent.com",
                "client_secret": "your-client-secret",
                "access_token": "ya29.a0AfB_...",
                "refresh_token": "1//04qX...",
                "token_expiry": "2023-07-28T12:34:56",
                "scope": "https://www.googleapis.com/auth/drive.file",
                "token_type": "Bearer",
                "additional_data": {"email": "user@example.com"}
            }
        }
    }

class OAuthConnectionCreate(BaseModel):
    """Model for creating a new OAuth connection"""
    user_id: str
    service_name: str
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scope: Optional[str] = None
    token_type: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class OAuthConnectionUpdate(BaseModel):
    """Model for updating an OAuth connection"""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scope: Optional[str] = None
    token_type: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class OAuthConnectionResponse(BaseModel):
    """Model for responding with OAuth connection details"""
    id: str
    user_id: str
    service_name: str
    client_id: str
    access_token: str  # Note: We'll only return this in certain contexts
    token_expiry: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    additional_data: Optional[Dict[str, Any]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "60d21b4967d0d8992e610c85",
                "user_id": "user123",
                "service_name": "google_drive",
                "client_id": "your-client-id.apps.googleusercontent.com",
                "access_token": "ya29.a0AfB_...",
                "token_expiry": "2023-07-28T12:34:56",
                "is_active": True,
                "created_at": "2023-07-27T12:34:56",
                "updated_at": "2023-07-27T12:34:56",
                "additional_data": {"email": "user@example.com"}
            }
        }
    }

# Helper functions for database operations
async def get_oauth_connection(db, user_id: str, service_name: str):
    """Get OAuth connection for a user and service"""
    connection = await db.oauth_connections.find_one({
        "user_id": user_id,
        "service_name": service_name,
        "is_active": True
    })
    return connection

async def create_oauth_connection(db, connection_data: OAuthConnectionCreate):
    """Create a new OAuth connection"""
    connection = connection_data.model_dump()
    connection["created_at"] = datetime.utcnow()
    connection["updated_at"] = datetime.utcnow()
    connection["is_active"] = True
    
    # Check if connection already exists
    existing = await db.oauth_connections.find_one({
        "user_id": connection["user_id"],
        "service_name": connection["service_name"]
    })
    
    if existing:
        # Update existing connection
        updated = await db.oauth_connections.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": {
                "access_token": connection["access_token"],
                "refresh_token": connection["refresh_token"],
                "token_expiry": connection["token_expiry"],
                "scope": connection["scope"],
                "token_type": connection["token_type"],
                "additional_data": connection["additional_data"],
                "updated_at": connection["updated_at"],
                "is_active": True
            }},
            return_document=ReturnDocument.AFTER
        )
        return updated
    else:
        # Create new connection
        result = await db.oauth_connections.insert_one(connection)
        return await db.oauth_connections.find_one({"_id": result.inserted_id})

async def update_oauth_connection(db, connection_id: str, update_data: OAuthConnectionUpdate):
    """Update an existing OAuth connection"""
    connection = await db.oauth_connections.find_one_and_update(
        {"_id": ObjectId(connection_id)},
        {"$set": update_data.model_dump(exclude_unset=True)},
        return_document=ReturnDocument.AFTER
    )
    return connection

async def deactivate_oauth_connection(db, user_id: str, service_name: str):
    """Deactivate an OAuth connection"""
    connection = await db.oauth_connections.find_one_and_update(
        {
            "user_id": user_id,
            "service_name": service_name
        },
        {"$set": {
            "is_active": False,
            "updated_at": datetime.utcnow()
        }},
        return_document=ReturnDocument.AFTER
    )
    return connection

async def list_user_connections(db, user_id: str):
    """List all active OAuth connections for a user"""
    cursor = db.oauth_connections.find({
        "user_id": user_id,
        "is_active": True
    })
    connections = await cursor.to_list(length=100)
    return connections 
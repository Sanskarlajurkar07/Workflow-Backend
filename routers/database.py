from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List
from models.database import (
    ConnectionCreate, 
    DatabaseConnection, 
    DatabaseConnectionResponse,
    MongoDBTest, 
    MySQLTest, 
    ConnectionTestResponse,
    MongoDBCredentials,
    MySQLCredentials
)
from routers.auth import get_current_user
from models.user import User
from bson import ObjectId
from datetime import datetime
import pymongo
import logging

# Set up logging
logger = logging.getLogger("workflow_api")

router = APIRouter(prefix="", tags=["database"])

# Get the database connections collection
async def get_connections_collection(request: Request):
    return request.app.mongodb["database_connections"]

# Get all connections for a user
@router.get("/connections", response_model=List[DatabaseConnectionResponse])
async def get_connections(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    connections_collection = await get_connections_collection(request)
    
    connections = await connections_collection.find({"user_id": current_user.id}).to_list(1000)
    return connections

# Get a specific connection
@router.get("/connections/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_connection(
    connection_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    connections_collection = await get_connections_collection(request)
    
    connection = await connections_collection.find_one({
        "_id": ObjectId(connection_id),
        "user_id": current_user.id
    })
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    # Convert ObjectId to string for response
    connection["id"] = str(connection["_id"])
    return connection

# Create a new MySQL connection - Temporarily disabled
@router.post("/mysql/connect", response_model=DatabaseConnectionResponse)
async def create_mysql_connection(
    connection: ConnectionCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="MySQL functionality is temporarily disabled"
    )

# Create a new MongoDB connection
@router.post("/mongodb/connect", response_model=DatabaseConnectionResponse)
async def create_mongodb_connection(
    connection: ConnectionCreate,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    connections_collection = await get_connections_collection(request)
    
    # Make sure the type is mongodb
    if connection.type != "mongodb":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection type must be mongodb"
        )
    
    # Test the connection first
    try:
        mongodb_credentials = connection.credentials
        if not isinstance(mongodb_credentials, MongoDBCredentials):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MongoDB credentials"
            )
        
        # Attempt to connect
        client = pymongo.MongoClient(mongodb_credentials.connection_uri)
        client.server_info()  # Will raise an exception if connection fails
        client.close()
    except Exception as e:
        logger.error(f"MongoDB connection error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to MongoDB: {str(e)}"
        )
    
    # Create new connection document
    now = datetime.utcnow()
    connection_id = ObjectId()
    connection_doc = {
        "_id": connection_id,
        "user_id": current_user.id,
        "name": connection.name,
        "type": "mongodb",
        "credentials": connection.credentials.dict(),
        "created_at": now,
        "updated_at": now
    }
    
    # Insert into database
    await connections_collection.insert_one(connection_doc)
    
    # Return the created connection
    connection_doc["id"] = str(connection_id)
    return connection_doc

# Test MySQL connection - Temporarily disabled
@router.post("/mysql/test", response_model=ConnectionTestResponse)
async def test_mysql_connection(
    test: MySQLTest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="MySQL functionality is temporarily disabled"
    )

# Test MongoDB connection
@router.post("/mongodb/test", response_model=ConnectionTestResponse)
async def test_mongodb_connection(
    test: MongoDBTest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    try:
        # Attempt to connect
        client = pymongo.MongoClient(test.connection_uri)
        
        # Test connection by getting server info
        server_info = client.server_info()
        
        # Close the connection
        client.close()
        
        return ConnectionTestResponse(
            success=True, 
            message=f"Connected to MongoDB version: {server_info.get('version', 'unknown')}"
        )
    except Exception as e:
        logger.error(f"MongoDB test connection error: {str(e)}")
        return ConnectionTestResponse(success=False, message=str(e))

# Delete a connection
@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    connections_collection = await get_connections_collection(request)
    
    result = await connections_collection.delete_one({
        "_id": ObjectId(connection_id),
        "user_id": current_user.id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or you don't have permission to delete it"
        )
    
    return {"message": "Connection deleted successfully"} 
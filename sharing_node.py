import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from models.workflow import NodeResult
from database import get_database
from bson import ObjectId

logger = logging.getLogger("workflow_api")

# Supported object types for sharing
SUPPORTED_OBJECT_TYPES = [
    "workflow", 
    "file", 
    "knowledge_base", 
    "dataset",
    "model"
]

async def handle_share_object_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request=None
) -> NodeResult:
    """Handler for share_object node type
    
    This node shares objects with other users within the system.
    """
    logger.info(f"Executing Share Object node {node_id}")
    
    # Get database from request
    if not request or not hasattr(request, 'app') or not hasattr(request.app, 'mongodb'):
        logger.error("Database not accessible in share_object node")
        return NodeResult(
            output={"error": "Database connection not available"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="Database connection not available",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Share Object")
        )
    
    db = request.app.mongodb
    
    # Extract parameters
    object_type = node_data.get("params", {}).get("objectType", "")
    object_id = node_data.get("params", {}).get("objectId", "")
    user_identifier = node_data.get("params", {}).get("userIdentifier", "")
    organization_name = node_data.get("params", {}).get("organizationName", "")
    expiry_days = node_data.get("params", {}).get("expiryDays", 0)  # 0 means no expiry
    access_level = node_data.get("params", {}).get("accessLevel", "read")  # read, edit, admin
    variable_name = node_data.get("params", {}).get("variableName", f"share_result_{node_id[:4]}")
    
    # Get user if available
    current_user = None
    if hasattr(request, "state") and hasattr(request.state, "user"):
        current_user = request.state.user
        
    # Validate parameters
    if not object_type or object_type not in SUPPORTED_OBJECT_TYPES:
        return NodeResult(
            output={"error": f"Invalid object type: {object_type}. Supported types: {', '.join(SUPPORTED_OBJECT_TYPES)}"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=f"Invalid object type: {object_type}",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Share Object")
        )
        
    if not user_identifier and not organization_name:
        return NodeResult(
            output={"error": "Either user identifier or organization name is required"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="Either user identifier or organization name is required",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Share Object")
        )
    
    try:
        # Get object from input or from specified ID
        target_object = None
        object_source = "input"
        
        if object_id:
            # Try to get object by ID from database
            object_collection = None
            
            if object_type == "workflow":
                object_collection = db.workflows
            elif object_type == "file":
                object_collection = db.files
            elif object_type == "knowledge_base":
                object_collection = db.knowledge_bases
            elif object_type == "dataset":
                object_collection = db.datasets
            elif object_type == "model":
                object_collection = db.models
            
            if object_collection:
                try:
                    target_object = await object_collection.find_one({"_id": ObjectId(object_id)})
                    object_source = "database"
                except:
                    # Try string ID
                    target_object = await object_collection.find_one({"_id": object_id})
                    object_source = "database"
        else:
            # Get from input
            target_object = inputs.get("input", {})
            
        if not target_object:
            return NodeResult(
                output={"error": f"Object not found with ID: {object_id}"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Object not found with ID: {object_id}",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "Share Object")
            )
            
        # Find target user(s)
        target_users = []
        
        if user_identifier:
            user = await db.users.find_one({"$or": [
                {"email": user_identifier},
                {"username": user_identifier},
                {"_id": user_identifier}
            ]})
            
            if user:
                target_users.append(user)
        
        if organization_name:
            org = await db.organizations.find_one({"name": organization_name})
            
            if org:
                org_users = await db.users.find({"organization_id": str(org["_id"])}).to_list(100)
                target_users.extend(org_users)
                
        if not target_users:
            return NodeResult(
                output={"error": "No target users found with the provided identifiers"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error="No target users found with the provided identifiers",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "Share Object")
            )
            
        # Create sharing records
        expiry_date = None
        if expiry_days > 0:
            expiry_date = datetime.utcnow() + timedelta(days=expiry_days)
            
        results = []
        
        for user in target_users:
            # Generate a sharing record
            share_record = {
                "object_type": object_type,
                "object_id": object_id if object_id else "dynamic_input",
                "shared_by": str(current_user["_id"]) if current_user else "system",
                "shared_with": str(user["_id"]),
                "access_level": access_level,
                "created_at": datetime.utcnow(),
                "expires_at": expiry_date,
                "is_active": True
            }
            
            # If sharing from input (not database), store a copy of the object
            if object_source == "input":
                # Generate an ID for the shared object
                object_hash = hashlib.md5(
                    (str(target_object) + str(datetime.utcnow())).encode()
                ).hexdigest()
                
                shared_object = {
                    "_id": object_hash,
                    "type": object_type,
                    "data": target_object,
                    "created_at": datetime.utcnow(),
                    "created_by": str(current_user["_id"]) if current_user else "system",
                    "shared_with": str(user["_id"])
                }
                
                # Insert shared object
                await db.shared_objects.insert_one(shared_object)
                
                # Update the record with the generated ID
                share_record["object_id"] = object_hash
            
            # Save sharing record
            share_result = await db.object_shares.insert_one(share_record)
            
            # Generate sharing URL if supported
            sharing_url = None
            if object_type == "workflow":
                sharing_url = f"/shared/workflow/{share_record['object_id']}?token={str(share_result.inserted_id)}"
            elif object_type == "file":
                sharing_url = f"/shared/file/{share_record['object_id']}?token={str(share_result.inserted_id)}"
            elif object_type == "knowledge_base":
                sharing_url = f"/shared/kb/{share_record['object_id']}?token={str(share_result.inserted_id)}"
                
            results.append({
                "user_id": str(user["_id"]),
                "user_email": user.get("email", ""),
                "user_name": user.get("name", user.get("username", "")),
                "share_id": str(share_result.inserted_id),
                "object_id": share_record["object_id"],
                "access_level": access_level,
                "expires_at": expiry_date.isoformat() if expiry_date else None,
                "sharing_url": sharing_url
            })
        
        # Prepare result
        result = {
            "success": True,
            "object_type": object_type,
            "shared_with_count": len(results),
            "shares": results
        }
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Share Object")
        )
        
    except Exception as e:
        logger.error(f"Error in Share Object node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Share Object")
        ) 
import logging
import os
import json
import base64
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

# Default save location configuration
DEFAULT_SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

# Ensure the default save directory exists
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)

async def handle_file_save_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for file_save node type
    
    This node saves file content to disk or to a storage backend.
    """
    logger.info(f"Executing File Save node {node_id}")
    
    # Extract parameters
    save_location = node_data.get("params", {}).get("saveLocation", "local")  # local, s3, azure, etc.
    path = node_data.get("params", {}).get("path", "")
    filename_template = node_data.get("params", {}).get("filename", "{original_filename}")
    create_directories = node_data.get("params", {}).get("createDirectories", True)
    overwrite_existing = node_data.get("params", {}).get("overwriteExisting", False)
    variable_name = node_data.get("params", {}).get("variableName", f"saved_file_{node_id[:4]}")
    storage_config = node_data.get("params", {}).get("storageConfig", {})
    add_timestamp = node_data.get("params", {}).get("addTimestamp", False)
    
    # Get input data
    input_data = inputs.get("input", {})
    
    if not input_data:
        return NodeResult(
            output={"error": "No input data provided"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="No input data provided",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "File Save")
        )
    
    try:
        # Extract file content and metadata
        file_content = None
        file_metadata = {}
        original_filename = "file"
        
        if isinstance(input_data, dict):
            if "content" in input_data:
                file_content = input_data.get("content")
                file_metadata = input_data.get("metadata", {})
                original_filename = file_metadata.get("filename", "file")
            else:
                # Try to find content in nested structure
                for key, value in input_data.items():
                    if isinstance(value, dict) and "content" in value:
                        file_content = value.get("content")
                        file_metadata = value.get("metadata", {})
                        original_filename = file_metadata.get("filename", "file")
                        break
        elif isinstance(input_data, str):
            # Assume it's the file content itself
            file_content = input_data
            original_filename = "file.txt"
            
        if not file_content:
            return NodeResult(
                output={"error": "No file content found in input"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error="No file content found in input",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "File Save")
            )
            
        # Prepare filename using template
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_vars = {
            "original_filename": original_filename,
            "node_id": node_id,
            "timestamp": timestamp,
            **file_metadata
        }
        
        # Format filename from template
        try:
            filename = filename_template.format(**filename_vars)
        except KeyError as e:
            filename = original_filename
            logger.warning(f"Filename template error: {str(e)}. Using original filename.")
            
        # Add timestamp if requested
        if add_timestamp:
            name_parts = os.path.splitext(filename)
            filename = f"{name_parts[0]}_{timestamp}{name_parts[1]}"
            
        # Determine the full save path
        if save_location == "local":
            # Local file system
            if not path:
                # Use default path
                save_path = DEFAULT_SAVE_DIR
            else:
                # Use specified path
                save_path = path
                
            # Create directories if needed
            if create_directories and not os.path.exists(save_path):
                os.makedirs(save_path, exist_ok=True)
                
            # Full file path
            full_path = os.path.join(save_path, filename)
            
            # Check if file exists
            if os.path.exists(full_path) and not overwrite_existing:
                # Append a number to filename
                name_parts = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(save_path, f"{name_parts[0]}_{counter}{name_parts[1]}")):
                    counter += 1
                filename = f"{name_parts[0]}_{counter}{name_parts[1]}"
                full_path = os.path.join(save_path, filename)
                
            # Save the file
            with open(full_path, "wb") as f:
                if isinstance(file_content, str):
                    # Check if it's base64 encoded
                    if file_metadata.get("encoding") == "base64":
                        try:
                            decoded_content = base64.b64decode(file_content)
                            f.write(decoded_content)
                        except Exception as e:
                            logger.error(f"Base64 decode error: {str(e)}")
                            f.write(file_content.encode("utf-8"))
                    else:
                        f.write(file_content.encode("utf-8"))
                else:
                    # Assume it's already bytes
                    f.write(file_content)
                    
            # Prepare result
            result = {
                "path": full_path,
                "filename": filename,
                "directory": save_path,
                "size_bytes": os.path.getsize(full_path),
                "url": f"file://{full_path}",
                "storage_type": "local"
            }
            
        elif save_location == "s3":
            # AWS S3 storage implementation
            try:
                import boto3
                from botocore.exceptions import NoCredentialsError
                
                # Get S3 configuration
                bucket_name = storage_config.get("bucket", "")
                aws_access_key = storage_config.get("accessKey", "")
                aws_secret_key = storage_config.get("secretKey", "")
                region_name = storage_config.get("region", "us-east-1")
                s3_path = path.lstrip("/")
                
                if not bucket_name:
                    raise ValueError("S3 bucket name is required")
                    
                # Create S3 client
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=region_name
                )
                
                # Prepare full path in S3
                if s3_path:
                    s3_key = f"{s3_path.rstrip('/')}/{filename}"
                else:
                    s3_key = filename
                    
                # Upload to S3
                if isinstance(file_content, str):
                    # Convert string to bytes
                    if file_metadata.get("encoding") == "base64":
                        upload_data = base64.b64decode(file_content)
                    else:
                        upload_data = file_content.encode("utf-8")
                else:
                    upload_data = file_content
                
                content_type = file_metadata.get("type", "")
                if not content_type:
                    content_type, _ = mimetypes.guess_type(filename)
                    
                s3_client.put_object(
                    Body=upload_data,
                    Bucket=bucket_name,
                    Key=s3_key,
                    ContentType=content_type or "application/octet-stream"
                )
                
                # Prepare result
                s3_url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{s3_key}"
                result = {
                    "path": s3_key,
                    "filename": filename,
                    "bucket": bucket_name,
                    "directory": s3_path,
                    "url": s3_url,
                    "storage_type": "s3"
                }
                
            except ImportError:
                return NodeResult(
                    output={"error": "boto3 package not installed. Please install it to use S3 storage."},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="boto3 package not installed. Please install it to use S3 storage.",
                    node_id=node_id,
                    node_name=node_data.get("params", {}).get("nodeName", "File Save")
                )
            except NoCredentialsError:
                return NodeResult(
                    output={"error": "AWS credentials not found or invalid"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="AWS credentials not found or invalid",
                    node_id=node_id,
                    node_name=node_data.get("params", {}).get("nodeName", "File Save")
                )
            except Exception as e:
                return NodeResult(
                    output={"error": f"S3 upload error: {str(e)}"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error=f"S3 upload error: {str(e)}",
                    node_id=node_id,
                    node_name=node_data.get("params", {}).get("nodeName", "File Save")
                )
                
        else:
            return NodeResult(
                output={"error": f"Unsupported storage location: {save_location}"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Unsupported storage location: {save_location}",
                node_id=node_id,
                node_name=node_data.get("params", {}).get("nodeName", "File Save")
            )
            
        # Add metadata to result if available
        if file_metadata:
            result["metadata"] = file_metadata
            
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "File Save")
        )
        
    except Exception as e:
        logger.error(f"Error in File Save node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "File Save")
        ) 
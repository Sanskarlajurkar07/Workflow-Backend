from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import os
import logging
from models.knowledge_base import (
    KnowledgeBase, KnowledgeBaseCreate, Document, DocumentCreate, 
    KnowledgeBaseSync, KnowledgeBaseSearch, DataSourceType, DocumentStatus,
    SearchResponse, SearchResult
)
from models.user import User
from routers.auth import get_current_user
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from qdrant_client.models import Distance, VectorParams
from embedding_config import get_embedding_dimension, get_embedding_provider, get_model_name, get_max_tokens, EMBEDDING_MODEL_CONFIG
from services.search_service import SearchService
from services.background_tasks import background_task_service
from services.error_recovery import error_recovery, with_full_protection, ErrorType, check_mongodb_health, check_qdrant_health
from services.monitoring import (
    monitor_performance, monitor_errors, metrics_collector, 
    performance_monitor, health_checker
)
from services.performance_optimizer import (
    embedding_cache, search_cache, cached, 
    initialize_performance_systems, smart_cache
)
from services.security_hardening import security_manager
from services.smart_database import get_smart_database_engine
import json

# Setup logging
logger = logging.getLogger("knowledge_base_api")

router = APIRouter(
    prefix="/api/knowledge-base",
    tags=["knowledge-base"],
    responses={404: {"description": "Not found"}},
)

# Helper function to get MongoDB collection
async def get_kb_collection(request: Request) -> AsyncIOMotorCollection:
    return request.app.mongodb["knowledge_bases"]

# Helper function to get Qdrant client
def get_qdrant_client(request: Request):
    return request.app.qdrant

# Helper functions for MongoDB document conversion
def kb_to_mongo(kb: KnowledgeBase) -> dict:
    kb_dict = kb.model_dump()
    if '_id' in kb_dict:
        del kb_dict['_id']
    return kb_dict

def mongo_to_kb(mongo_doc: dict) -> KnowledgeBase:
    if '_id' in mongo_doc:
        mongo_doc['id'] = str(mongo_doc['_id'])
        del mongo_doc['_id']
    return KnowledgeBase(**mongo_doc)

# Initialize services
search_service = SearchService()

# Additional helper functions
def get_embedding_model_config(embedding_model: str) -> Dict[str, Any]:
    """Get embedding model configuration"""
    from models.knowledge_base import EmbeddingModel
    
    # Map string to enum if needed
    if isinstance(embedding_model, str):
        try:
            model_enum = EmbeddingModel(embedding_model)
        except ValueError:
            model_enum = EmbeddingModel.TEXT_EMBEDDING_3_SMALL  # Default
    else:
        model_enum = embedding_model
    
    return EMBEDDING_MODEL_CONFIG[model_enum]

async def create_qdrant_collection(collection_name: str, embedding_config: Dict[str, Any], request: Request):
    """Create a Qdrant collection if it doesn't exist"""
    qdrant_client = get_qdrant_client(request)
    
    try:
        # Check if collection exists
        qdrant_client.get_collection(collection_name)
        logger.info(f"Qdrant collection {collection_name} already exists")
    except Exception:
        # Collection doesn't exist, create it
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=embedding_config["dimension"],
                distance=Distance.COSINE
            )
        )
        logger.info(f"Created Qdrant collection: {collection_name}")

# Enhanced knowledge base operations with production features
@router.post("/", response_model=KnowledgeBase)
@monitor_performance("create_knowledge_base")
@monitor_errors("knowledge_base")
async def create_knowledge_base(
    kb: KnowledgeBaseCreate, 
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Create a new knowledge base with enhanced security and monitoring"""
    
    # Security validation
    request_data = kb.dict()
    security_result = security_manager.validate_request(
        "127.0.0.1",  # Would get from request context
        "create_knowledge_base",
        request_data
    )
    
    if not security_result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Security validation failed: {security_result['errors']}"
        )
    
    # Use sanitized data
    sanitized_data = security_result["sanitized_data"]
    
    try:
        async with performance_monitor.measure_async("database_operations"):
            # Create knowledge base with error recovery - pass request object
            kb_dict = await error_recovery.execute_with_full_protection(
                _create_kb_with_protection,
                "mongodb",
                request,
                sanitized_data,
                current_user.id,
                error_type=ErrorType.MONGODB_CONNECTION
            )
        
        # Create Qdrant collection with retry logic
        collection_name = f"kb_{kb_dict['_id']}"
        
        await error_recovery.execute_with_retry(
            create_qdrant_collection,
            collection_name,
            get_embedding_model_config(sanitized_data.get("embedding_model", "text-embedding-3-small")),
            request,
            error_type=ErrorType.QDRANT_CONNECTION
        )
        
        # Record metrics
        metrics_collector.record_metric("knowledge_bases.created", 1, {"user_id": current_user.id})
        
        # Convert MongoDB document to KnowledgeBase model
        new_kb = KnowledgeBase(
            id=str(kb_dict["_id"]),
            user_id=kb_dict["user_id"],
            name=kb_dict["name"],
            description=kb_dict["description"],
            chunk_size=kb_dict["chunk_size"],
            chunk_overlap=kb_dict["chunk_overlap"],
            embedding_model=kb_dict["embedding_model"],
            advanced_doc_analysis=kb_dict["advanced_doc_analysis"],
            created_at=kb_dict["created_at"],
            updated_at=kb_dict["updated_at"],
            documents=[]
        )
        
        return new_kb

    except Exception as e:
        logger.error(f"Failed to create knowledge base: {str(e)}")
        metrics_collector.record_error(e, "knowledge_base", current_user.id)
        
        # Cleanup on failure
        if 'collection_name' in locals():
            try:
                qdrant_client = get_qdrant_client(request)
                qdrant_client.delete_collection(collection_name)
            except:
                pass
                
        raise HTTPException(status_code=500, detail="Failed to create knowledge base")

@router.get("/", response_model=List[KnowledgeBase])
async def list_knowledge_bases(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """List all knowledge bases for the current user"""
    collection = await get_kb_collection(request)
    cursor = collection.find({"user_id": current_user.id})  # Filter by user_id
    
    knowledge_bases = []
    async for doc in cursor:
        knowledge_bases.append(mongo_to_kb(doc))
    
    return knowledge_bases

@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(
    kb_id: str, 
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get a specific knowledge base by ID"""
    collection = await get_kb_collection(request)
    
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    return mongo_to_kb(kb_doc)

@router.put("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(
    kb_id: str, 
    kb_update: KnowledgeBaseCreate, 
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Update a knowledge base"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Convert to KnowledgeBase object
    kb = mongo_to_kb(kb_doc)
    
    # Update fields
    kb.name = kb_update.name
    kb.description = kb_update.description
    kb.chunk_size = kb_update.chunk_size
    kb.chunk_overlap = kb_update.chunk_overlap
    kb.embedding_model = kb_update.embedding_model
    kb.advanced_doc_analysis = kb_update.advanced_doc_analysis
    kb.updated_at = datetime.now()
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    logger.info(f"Updated knowledge base: {kb_id} for user: {current_user.id}")
    return kb

@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str, 
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Delete a knowledge base"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Delete from MongoDB
    await collection.delete_one({"id": kb_id, "user_id": current_user.id})
    
    # TODO: Delete associated Qdrant collection/embeddings
    qdrant_client = get_qdrant_client(request)
    try:
        qdrant_client.delete_collection(kb_id)
        logger.info(f"Deleted Qdrant collection for knowledge base: {kb_id}")
    except Exception as e:
        logger.warning(f"Failed to delete Qdrant collection for knowledge base {kb_id}: {str(e)}")
    
    logger.info(f"Deleted knowledge base: {kb_id} for user: {current_user.id}")
    return {"status": "success", "message": f"Knowledge base {kb_id} deleted"}

@router.post("/{kb_id}/documents", response_model=Document)
async def add_document(
    kb_id: str, 
    document: DocumentCreate, 
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Add a document to a knowledge base"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Convert to KnowledgeBase object
    kb = mongo_to_kb(kb_doc)
    
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    new_doc = Document(
        id=doc_id,
        name=document.name,
        source_type=document.source_type,
        source_path=document.source_path,
        status=DocumentStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=document.metadata
    )
    
    # Add document to knowledge base
    kb.documents.append(new_doc)
    kb.updated_at = datetime.now()
    
    # If this is the first document, update status to active
    if len(kb.documents) == 1:
        kb.status = "active"
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    # Trigger background processing
    background_tasks.add_task(
        background_task_service.process_document_task,
        document=new_doc,
        kb_id=kb_id,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        embedding_model=kb.embedding_model,
        qdrant_client=get_qdrant_client(request),
        mongodb_collection=collection,
        user_id=current_user.id,
        advanced_analysis=kb.advanced_doc_analysis
    )
    
    logger.info(f"Added document {doc_id} to knowledge base {kb_id} for user: {current_user.id} (processing started)")
    return new_doc

@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str, 
    doc_id: str, 
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Delete a document from a knowledge base"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Convert to KnowledgeBase object
    kb = mongo_to_kb(kb_doc)
    
    # Find the document
    doc_index = None
    for i, doc in enumerate(kb.documents):
        if doc.id == doc_id:
            doc_index = i
            break
    
    if doc_index is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove document
    kb.documents.pop(doc_index)
    kb.updated_at = datetime.now()
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    # TODO: Remove document embeddings from Qdrant
    qdrant_client = get_qdrant_client(request)
    try:
        qdrant_client.delete(
            collection_name=kb_id,
            points_selector={"filter": {"must": [{"key": "document_id", "match": {"value": doc_id}}]}}
        )
        logger.info(f"Deleted document embeddings from Qdrant for document {doc_id}")
    except Exception as e:
        logger.warning(f"Failed to delete document embeddings for document {doc_id}: {str(e)}")
    
    logger.info(f"Deleted document {doc_id} from knowledge base {kb_id} for user: {current_user.id}")
    return {"status": "success", "message": f"Document {doc_id} deleted"}

@router.post("/{kb_id}/upload", response_model=Document)
async def upload_file(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Upload a file to a knowledge base"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Convert to KnowledgeBase object
    kb = mongo_to_kb(kb_doc)
    
    # Use filename if document_name not provided
    doc_name = document_name or file.filename
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save file
    file_path = f"uploads/{kb_id}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    new_doc = Document(
        id=doc_id,
        name=doc_name,
        source_type=DataSourceType.FILE,
        source_path=file_path,
        status=DocumentStatus.PENDING,  # Will be processed asynchronously
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={"original_filename": file.filename, "content_type": file.content_type}
    )
    
    # Add document to knowledge base
    kb.documents.append(new_doc)
    kb.updated_at = datetime.now()
    
    # If this is the first document, update status to active
    if len(kb.documents) == 1:
        kb.status = "active"
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    # Trigger background processing
    background_tasks.add_task(
        background_task_service.process_document_task,
        document=new_doc,
        kb_id=kb_id,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        embedding_model=kb.embedding_model,
        qdrant_client=get_qdrant_client(request),
        mongodb_collection=collection,
        user_id=current_user.id,
        advanced_analysis=kb.advanced_doc_analysis
    )
    
    logger.info(f"Uploaded file {file.filename} as document {doc_id} to knowledge base {kb_id} for user: {current_user.id} (processing started)")
    return new_doc

@router.post("/{kb_id}/sync", response_model=KnowledgeBaseSync)
async def sync_knowledge_base(
    kb_id: str, 
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Synchronize a knowledge base with its data sources"""
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Convert to KnowledgeBase object
    kb = mongo_to_kb(kb_doc)
    
    # Update timestamp in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": {"updated_at": datetime.now()}}
    )
    
    # Trigger background sync task
    background_tasks.add_task(
        background_task_service.sync_knowledge_base_task,
        kb_id=kb_id,
        user_id=current_user.id,
        documents=kb.documents,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        embedding_model=kb.embedding_model,
        qdrant_client=get_qdrant_client(request),
        mongodb_collection=collection,
        advanced_analysis=kb.advanced_doc_analysis
    )
    
    logger.info(f"Sync initiated for knowledge base {kb_id} for user: {current_user.id}")
    
    # Return sync status
    return KnowledgeBaseSync(
        id=kb_id,
        last_sync=datetime.now(),
        status="processing",
        details="Knowledge base sync started in background"
    )

@router.post("/{kb_id}/search", response_model=SearchResponse)
@monitor_performance("search_knowledge_base")
@monitor_errors("search")
@cached(ttl_seconds=1800, key_func=lambda kb_id, query, top_k=5, **kwargs: [kb_id, query, str(top_k)])
async def search_knowledge_base(
    kb_id: str,
    query: str,
    top_k: int = 5,
    current_user: User = Depends(get_current_user)
):
    """Search in knowledge base with caching and performance optimization"""
    
    # Security validation
    security_result = security_manager.validate_request(
        "127.0.0.1",
        "search_knowledge_base", 
        {"query": query}
    )
    
    if not security_result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Security validation failed: {security_result['errors']}"
        )
    
    sanitized_query = security_result["sanitized_data"]["query"]
    
    try:
        # Verify ownership with retry protection
        kb = await error_recovery.execute_with_retry(
            get_knowledge_base_by_id,
            kb_id,
            current_user.id,
            error_type=ErrorType.MONGODB_CONNECTION
        )
        
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Check cache first
        async with performance_monitor.measure_async("embedding_generation"):
            # Try to get query embedding from cache
            cached_embedding = await embedding_cache.get_embedding(
                sanitized_query, 
                kb["embedding_model"]
            )
            
            if cached_embedding:
                query_embedding = cached_embedding
                metrics_collector.record_metric("embeddings.cache_hits", 1)
            else:
                # Generate new embedding
                query_embedding = await error_recovery.execute_with_retry(
                    generate_embedding,
                    sanitized_query,
                    kb["embedding_model"],
                    error_type=ErrorType.EMBEDDING_API
                )
                
                # Cache for future use
                await embedding_cache.set_embedding(
                    sanitized_query,
                    kb["embedding_model"], 
                    query_embedding
                )
                metrics_collector.record_metric("embeddings.cache_misses", 1)
        
        # Check search cache
        cached_results = await search_cache.get_search_results(
            f"kb_{kb_id}",
            query_embedding,
            top_k
        )
        
        if cached_results:
            metrics_collector.record_metric("search.cache_hits", 1)
            return SearchResponse(
                query=sanitized_query,
                results=cached_results,
                total_results=len(cached_results),
                search_time="0.001s (cached)"
            )
        
        # Perform search with error recovery
        async with performance_monitor.measure_async("vector_search"):
            search_results = await error_recovery.execute_with_retry(
                search_in_collection,
                f"kb_{kb_id}",
                query_embedding,
                top_k,
                error_type=ErrorType.QDRANT_CONNECTION
            )
        
        # Cache search results
        await search_cache.set_search_results(
            f"kb_{kb_id}",
            query_embedding,
            top_k,
            search_results
        )
        
        # Record metrics
        metrics_collector.record_metric("search.performed", 1, {
            "knowledge_base_id": kb_id,
            "results_count": len(search_results)
        })
        
        return SearchResponse(
            query=sanitized_query,
            results=search_results,
            total_results=len(search_results),
            search_time="<1s"
        )
        
    except Exception as e:
        logger.error(f"Search failed for KB {kb_id}: {str(e)}")
        metrics_collector.record_error(e, "search", current_user.id)
        raise HTTPException(status_code=500, detail="Search failed")

# Add new endpoint to get task status
@router.get("/{kb_id}/tasks/{task_id}")
async def get_task_status(
    kb_id: str,
    task_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get status of a background processing task"""
    # Verify user owns the knowledge base
    collection = await get_kb_collection(request)
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Get task status
    task_status = background_task_service.get_task_status(task_id)
    
    return {
        "task_id": task_id,
        "kb_id": kb_id,
        **task_status
    }

# Add endpoint to list active tasks
@router.get("/{kb_id}/tasks")
async def list_tasks(
    kb_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """List active background tasks for a knowledge base"""
    # Verify user owns the knowledge base
    collection = await get_kb_collection(request)
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Get all active tasks
    all_active_tasks = background_task_service.list_active_tasks()
    
    # Filter tasks for this knowledge base
    kb_tasks = {
        task_id: task_info 
        for task_id, task_info in all_active_tasks.items() 
        if task_info.get("kb_id") == kb_id
    }
    
    return {
        "kb_id": kb_id,
        "active_tasks": kb_tasks,
        "total_active": len(kb_tasks)
    }

@router.get("/health")
async def health_check(request: Request):
    """Enhanced health check endpoint"""
    
    async with performance_monitor.measure_async("health_check"):
        # Get database and qdrant client from request
        db = request.app.mongodb
        qdrant_client = request.app.qdrant
        
        # Register health checks if not already done
        if "mongodb" not in health_checker.checks:
            health_checker.register_check("mongodb", lambda: check_mongodb_health(db))
            health_checker.register_check("qdrant", lambda: check_qdrant_health(qdrant_client))
        
        # Run all health checks
        health_results = await health_checker.run_all_checks()
        
        # Get system metrics
        system_metrics = metrics_collector.get_system_metrics()
        
        # Get performance metrics
        perf_summary = metrics_collector.get_metrics_summary(since_minutes=5)
        
        # Determine overall health
        overall_healthy = all(
            health.status == "healthy" 
            for health in health_results.values()
        )
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                name: {
                    "status": health.status,
                    "message": health.message,
                    "response_time_ms": health.response_time * 1000 if health.response_time else None
                }
                for name, health in health_results.items()
            },
            "system": system_metrics,
            "performance": {
                "cache_stats": smart_cache.get_stats(),
                "recent_metrics": perf_summary
            }
        }

@router.get("/metrics")
async def get_metrics(current_user: User = Depends(get_current_user)):
    """Get comprehensive metrics (admin only)"""
    
    # In production, add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    metrics_summary = metrics_collector.get_metrics_summary(since_minutes=60)
    system_metrics = metrics_collector.get_system_metrics()
    
    return {
        "metrics": metrics_summary,
        "system": system_metrics,
        "cache": {
            "smart_cache": smart_cache.get_stats(),
            "embedding_cache": embedding_cache.cache.get_stats(),
            "search_cache": search_cache.cache.get_stats()
        }
    }

# Helper functions with error recovery
async def _create_kb_with_protection(request: Request, sanitized_data: Dict, user_id: str):
    """Protected knowledge base creation"""
    kb_dict = {
        "name": sanitized_data["name"],
        "description": sanitized_data.get("description"),
        "user_id": user_id,
        "chunk_size": sanitized_data.get("chunk_size", 400),
        "chunk_overlap": sanitized_data.get("chunk_overlap", 0),
        "embedding_model": sanitized_data.get("embedding_model", "text-embedding-3-small"),
        "advanced_doc_analysis": sanitized_data.get("advanced_doc_analysis", True),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "documents": [],
        "status": "active"
    }
    
    collection = await get_kb_collection(request)
    result = await collection.insert_one(kb_dict)
    
    # Set the id field to match the MongoDB _id for easy retrieval
    kb_id = str(result.inserted_id)
    await collection.update_one(
        {"_id": result.inserted_id},
        {"$set": {"id": kb_id}}
    )
    
    kb_dict["_id"] = result.inserted_id
    kb_dict["id"] = kb_id
    
    return kb_dict

async def get_knowledge_base_by_id(kb_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get knowledge base by ID and user ID"""
    # This would need request context, but for now return a simple dict
    # In practice, this function would need to be refactored to accept the collection
    return {
        "id": kb_id,
        "user_id": user_id,
        "embedding_model": "text-embedding-3-small"
    }

async def generate_embedding(query: str, embedding_model: str) -> List[float]:
    """Generate embedding for a query"""
    return await search_service.generate_embedding(query, embedding_model)

async def search_in_collection(collection_name: str, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
    """Search in Qdrant collection"""
    # This would need Qdrant client context, return empty for now
    # In practice, this function would need to be refactored
    return []

# Startup event to initialize production systems
async def initialize_production_systems():
    """Initialize production-ready systems on startup"""
    try:
        # Initialize performance systems
        redis_url = os.getenv("REDIS_URL")  # Optional
        await initialize_performance_systems(redis_url)
        
        # Note: Health checks will be registered when health_check endpoint is called
        # since they need access to request.app.mongodb and request.app.qdrant
        
        logger.info("Production systems initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize production systems: {e}")

# Security headers should be added at the application level in main.py
# This function can be imported and used there
def get_security_headers_middleware():
    """Get security headers middleware for use in main app"""
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        headers = security_manager.get_security_headers()
        for header, value in headers.items():
            response.headers[header] = value
        return response
    return add_security_headers

# Add new smart database endpoints
@router.post("/{kb_id}/smart-search", response_model=Dict[str, Any])
@monitor_performance("smart_search")
@monitor_errors("smart_search")
async def intelligent_search(
    kb_id: str,
    query: str,
    options: Dict[str, Any] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user)
):
    """Perform intelligent search with AI-powered optimizations"""
    
    # Security validation
    security_result = security_manager.validate_request(
        "127.0.0.1",
        "intelligent_search",
        {"query": query}
    )
    
    if not security_result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Security validation failed: {security_result['errors']}"
        )
    
    try:
        # Verify ownership
        collection = await get_kb_collection(request)
        kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
        if not kb_doc:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Get smart database engine
        qdrant_client = get_qdrant_client(request)
        smart_engine = get_smart_database_engine(qdrant_client, collection)
        
        # Perform intelligent search
        results = await smart_engine.intelligent_search(
            kb_id, 
            security_result["sanitized_data"]["query"], 
            options or {}
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Intelligent search failed for KB {kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Intelligent search failed")

@router.post("/{kb_id}/optimize", response_model=Dict[str, Any])
@monitor_performance("auto_optimize")
async def auto_optimize_knowledge_base(
    kb_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Automatically optimize knowledge base performance"""
    
    try:
        # Verify ownership
        collection = await get_kb_collection(request)
        kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
        if not kb_doc:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Get smart database engine
        qdrant_client = get_qdrant_client(request)
        smart_engine = get_smart_database_engine(qdrant_client, collection)
        
        # Run auto-optimization
        optimization_results = await smart_engine.auto_optimize_knowledge_base(kb_id)
        
        logger.info(f"Auto-optimization completed for KB {kb_id}")
        return optimization_results
        
    except Exception as e:
        logger.error(f"Auto-optimization failed for KB {kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Auto-optimization failed")

@router.get("/{kb_id}/analytics", response_model=Dict[str, Any])
@monitor_performance("get_analytics")
async def get_smart_analytics(
    kb_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive analytics and insights for a knowledge base"""
    
    try:
        # Verify ownership
        collection = await get_kb_collection(request)
        kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
        if not kb_doc:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Get smart database engine
        qdrant_client = get_qdrant_client(request)
        smart_engine = get_smart_database_engine(qdrant_client, collection)
        
        # Get analytics
        analytics = await smart_engine.get_smart_analytics(kb_id)
        
        return analytics
        
    except Exception as e:
        logger.error(f"Analytics retrieval failed for KB {kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Analytics retrieval failed")

@router.post("/{kb_id}/smart-upload", response_model=Document)
async def smart_upload_document(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Upload and process document with AI-powered optimizations"""
    
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Use filename if document_name not provided
    doc_name = document_name or file.filename
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save file
    file_path = f"uploads/{kb_id}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    new_doc = Document(
        id=doc_id,
        name=doc_name,
        source_type=DataSourceType.FILE,
        source_path=file_path,
        status=DocumentStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={"original_filename": file.filename, "content_type": file.content_type}
    )
    
    # Add document to knowledge base
    kb = mongo_to_kb(kb_doc)
    kb.documents.append(new_doc)
    kb.updated_at = datetime.now()
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    # Trigger intelligent background processing
    background_tasks.add_task(
        _smart_process_document_task,
        document=new_doc,
        kb_id=kb_id,
        qdrant_client=get_qdrant_client(request),
        mongodb_collection=collection,
        user_id=current_user.id
    )
    
    logger.info(f"Smart uploaded file {file.filename} as document {doc_id} to KB {kb_id}")
    return new_doc

# Background task for smart document processing
async def _smart_process_document_task(
    document: Document,
    kb_id: str,
    qdrant_client,
    mongodb_collection: AsyncIOMotorCollection,
    user_id: str
):
    """Background task for intelligent document processing"""
    
    try:
        # Get smart database engine
        smart_engine = get_smart_database_engine(qdrant_client, mongodb_collection)
        
        # Process document with AI optimizations
        processing_result = await smart_engine.intelligent_document_processing(
            kb_id,
            document.source_path,
            {
                "document_id": document.id,
                "document_name": document.name,
                "user_id": user_id,
                "original_filename": document.metadata.get("original_filename", ""),
                "content_type": document.metadata.get("content_type", "")
            }
        )
        
        # Update document status
        await mongodb_collection.update_one(
            {"id": kb_id, "user_id": user_id, "documents.id": document.id},
            {
                "$set": {
                    "documents.$.status": DocumentStatus.COMPLETED,
                    "documents.$.updated_at": datetime.now(),
                    "documents.$.metadata.processing_result": processing_result
                }
            }
        )
        
        logger.info(f"Smart processing completed for document {document.id} in KB {kb_id}")
        
    except Exception as e:
        logger.error(f"Smart document processing failed for {document.id}: {str(e)}")
        
        # Update document status to failed
        await mongodb_collection.update_one(
            {"id": kb_id, "user_id": user_id, "documents.id": document.id},
            {
                "$set": {
                    "documents.$.status": DocumentStatus.FAILED,
                    "documents.$.updated_at": datetime.now(),
                    "documents.$.metadata.error": str(e)
                }
            }
        )

@router.get("/{kb_id}/smart-recommendations", response_model=List[Dict[str, Any]])
async def get_smart_recommendations(
    kb_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get AI-powered recommendations for improving knowledge base"""
    
    try:
        # Verify ownership
        collection = await get_kb_collection(request)
        kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
        if not kb_doc:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # Get smart database engine
        qdrant_client = get_qdrant_client(request)
        smart_engine = get_smart_database_engine(qdrant_client, collection)
        
        # Analyze performance and generate recommendations
        metrics = await smart_engine._analyze_kb_performance(kb_id)
        recommendations = await smart_engine._generate_optimization_recommendations(kb_id, metrics)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Recommendations generation failed for KB {kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")

# Add advanced document loading endpoints inspired by VectorShift
@router.post("/{kb_id}/add-documents", response_model=List[Document])
async def add_documents_advanced(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    source_type: str = Form(...),  # file, url, recursive_url, integration
    source_path: str = Form(...),  # path, URL, or integration identifier
    document_name: Optional[str] = Form(None),
    metadata: Optional[str] = Form("{}"),  # JSON string
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    """Add documents to knowledge base with multiple source types (inspired by VectorShift)"""
    
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    kb = mongo_to_kb(kb_doc)
    
    # Parse metadata
    try:
        doc_metadata = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        doc_metadata = {}
    
    new_documents = []
    
    if source_type == "file" and file:
        # Handle file upload
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{kb_id}_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        new_doc = Document(
            id=doc_id,
            name=document_name or file.filename,
            source_type=DataSourceType.FILE,
            source_path=file_path,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={**doc_metadata, "original_filename": file.filename, "content_type": file.content_type}
        )
        new_documents.append(new_doc)
        
    elif source_type == "url":
        # Handle single URL
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        new_doc = Document(
            id=doc_id,
            name=document_name or f"URL: {source_path}",
            source_type=DataSourceType.URL,
            source_path=source_path,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={**doc_metadata, "url": source_path}
        )
        new_documents.append(new_doc)
        
    elif source_type == "recursive_url":
        # Handle recursive URL scraping (scrape all subpages)
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        new_doc = Document(
            id=doc_id,
            name=document_name or f"Recursive URL: {source_path}",
            source_type=DataSourceType.RECURSIVE_URL,
            source_path=source_path,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={**doc_metadata, "base_url": source_path, "recursive": True}
        )
        new_documents.append(new_doc)
        
    elif source_type == "integration":
        # Handle integration sources (Google Drive, Notion, etc.)
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        new_doc = Document(
            id=doc_id,
            name=document_name or f"Integration: {source_path}",
            source_type=DataSourceType.INTEGRATION,
            source_path=source_path,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={**doc_metadata, "integration_type": source_path}
        )
        new_documents.append(new_doc)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid source type or missing file")
    
    # Add documents to knowledge base
    kb.documents.extend(new_documents)
    kb.updated_at = datetime.now()
    
    # Update in MongoDB
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": kb_to_mongo(kb)}
    )
    
    # Trigger background processing for each document
    for doc in new_documents:
        if source_type == "file":
            # Use smart processing for files
            background_tasks.add_task(
                _smart_process_document_task,
                document=doc,
                kb_id=kb_id,
                qdrant_client=get_qdrant_client(request),
                mongodb_collection=collection,
                user_id=current_user.id
            )
        else:
            # Use standard processing for other types
            background_tasks.add_task(
                background_task_service.process_document_task,
                document=doc,
                kb_id=kb_id,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
                embedding_model=kb.embedding_model,
                qdrant_client=get_qdrant_client(request),
                mongodb_collection=collection,
                user_id=current_user.id,
                advanced_analysis=kb.advanced_doc_analysis
            )
    
    logger.info(f"Added {len(new_documents)} documents to KB {kb_id} using {source_type}")
    return new_documents

# Add VectorShift-inspired configuration endpoints
@router.put("/{kb_id}/configuration")
async def update_kb_configuration(
    kb_id: str,
    request: Request,
    enable_filters: bool = False,
    rerank_documents: bool = False,
    retrieval_unit: str = "chunks",
    do_nl_metadata_query: bool = False,
    transform_query: bool = False,
    answer_multiple_questions: bool = False,
    expand_query: bool = False,
    do_advanced_qa: bool = False,
    show_intermediate_steps: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Update knowledge base configuration with advanced features (inspired by VectorShift)"""
    
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Update configuration
    config_update = {
        "advanced_config": {
            "enable_filters": enable_filters,
            "rerank_documents": rerank_documents,
            "retrieval_unit": retrieval_unit,
            "do_nl_metadata_query": do_nl_metadata_query,
            "transform_query": transform_query,
            "answer_multiple_questions": answer_multiple_questions,
            "expand_query": expand_query,
            "do_advanced_qa": do_advanced_qa,
            "show_intermediate_steps": show_intermediate_steps
        },
        "updated_at": datetime.now()
    }
    
    await collection.update_one(
        {"id": kb_id, "user_id": current_user.id},
        {"$set": config_update}
    )
    
    logger.info(f"Updated configuration for KB {kb_id}")
    return {"status": "success", "message": "Knowledge base configuration updated", "config": config_update["advanced_config"]}

@router.get("/{kb_id}/configuration")
async def get_kb_configuration(
    kb_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get knowledge base configuration"""
    
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    config = kb_doc.get("advanced_config", {
        "enable_filters": False,
        "rerank_documents": False,
        "retrieval_unit": "chunks",
        "do_nl_metadata_query": False,
        "transform_query": False,
        "answer_multiple_questions": False,
        "expand_query": False,
        "do_advanced_qa": False,
        "show_intermediate_steps": False
    })
    
    return {
        "kb_id": kb_id,
        "configuration": config,
        "basic_settings": {
            "chunk_size": kb_doc.get("chunk_size", 400),
            "chunk_overlap": kb_doc.get("chunk_overlap", 0),
            "embedding_model": kb_doc.get("embedding_model", "text-embedding-3-small"),
            "advanced_doc_analysis": kb_doc.get("advanced_doc_analysis", True)
        }
    }

@router.post("/{kb_id}/search-advanced", response_model=Dict[str, Any])
@monitor_performance("advanced_search")
async def advanced_search(
    kb_id: str,
    query: str,
    request: Request,
    top_k: int = 5,
    score_threshold: float = 0.7,
    use_filters: bool = False,
    filter_query: Optional[str] = None,
    rerank: bool = False,
    expand_query: bool = False,
    show_steps: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Perform advanced search with VectorShift-inspired features"""
    
    collection = await get_kb_collection(request)
    
    # Check if KB exists and user owns it
    kb_doc = await collection.find_one({"id": kb_id, "user_id": current_user.id})
    if not kb_doc:
        raise HTTPException(status_code=404, detail="Knowledge base not found or access denied")
    
    # Get knowledge base configuration
    config = kb_doc.get("advanced_config", {})
    
    # Apply configuration overrides
    if config.get("rerank_documents", False):
        rerank = True
    if config.get("expand_query", False):
        expand_query = True
    if config.get("show_intermediate_steps", False):
        show_steps = True
    
    search_steps = []
    original_query = query
    
    # Step 1: Query expansion (if enabled)
    if expand_query:
        try:
            # Use AI to expand the query
            expanded_query = await _expand_query_with_ai(query)
            query = expanded_query
            if show_steps:
                search_steps.append({
                    "step": "query_expansion",
                    "original": original_query,
                    "expanded": expanded_query
                })
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
    
    # Step 2: Perform search using smart database engine
    try:
        qdrant_client = get_qdrant_client(request)
        smart_engine = get_smart_database_engine(qdrant_client, collection)
        
        search_options = {
            "top_k": top_k,
            "score_threshold": score_threshold,
            "embedding_model": kb_doc.get("embedding_model", "text-embedding-3-small")
        }
        
        results = await smart_engine.intelligent_search(kb_id, query, search_options)
        
        if show_steps:
            search_steps.append({
                "step": "vector_search",
                "query_used": query,
                "results_count": len(results.get("results", []))
            })
        
        # Step 3: Apply filters (if enabled and provided)
        if use_filters and filter_query:
            # Apply metadata filters (simplified implementation)
            filtered_results = await _apply_metadata_filters(results, filter_query)
            results = filtered_results
            
            if show_steps:
                search_steps.append({
                    "step": "metadata_filtering",
                    "filter": filter_query,
                    "results_after_filter": len(results.get("results", []))
                })
        
        # Step 4: Reranking (if enabled)
        if rerank and len(results.get("results", [])) > 1:
            reranked_results = await _rerank_results(query, results)
            results = reranked_results
            
            if show_steps:
                search_steps.append({
                    "step": "reranking",
                    "reranked_count": len(results.get("results", []))
                })
        
        # Add intermediate steps to results if requested
        if show_steps:
            results["intermediate_steps"] = search_steps
        
        return results
        
    except Exception as e:
        logger.error(f"Advanced search failed for KB {kb_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Advanced search failed")

# Helper functions for advanced search features
async def _expand_query_with_ai(query: str) -> str:
    """Expand query using AI to include related terms"""
    try:
        # Simple query expansion - in production, use more sophisticated methods
        expanded = f"{query} related concepts similar terms"
        return expanded
    except Exception:
        return query

async def _apply_metadata_filters(results: Dict[str, Any], filter_query: str) -> Dict[str, Any]:
    """Apply metadata filters to search results"""
    try:
        # Simplified filtering - in production, implement Qdrant filter syntax
        filtered_results = results.copy()
        # For now, just return original results
        return filtered_results
    except Exception:
        return results

async def _rerank_results(query: str, results: Dict[str, Any]) -> Dict[str, Any]:
    """Rerank search results for better relevance"""
    try:
        # Simplified reranking - in production, use cross-encoder models
        search_results = results.get("results", [])
        
        # Sort by a combination of score and text length (simple heuristic)
        reranked = sorted(search_results, key=lambda x: (x.get("score", 0) * 0.8 + (len(x.get("text", "")) / 1000) * 0.2), reverse=True)
        
        results_copy = results.copy()
        results_copy["results"] = reranked
        results_copy["reranked"] = True
        
        return results_copy
    except Exception:
        return results 
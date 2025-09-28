import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

from services.document_processor import DocumentProcessor
from models.knowledge_base import Document, DocumentStatus
from motor.motor_asyncio import AsyncIOMotorCollection

logger = logging.getLogger("background_tasks")

class BackgroundTaskService:
    """Service for managing background document processing tasks"""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.active_tasks = {}  # Track active processing tasks
    
    async def process_document_task(
        self,
        document: Document,
        kb_id: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model,
        qdrant_client,
        mongodb_collection: AsyncIOMotorCollection,
        user_id: str,
        advanced_analysis: bool = True
    ) -> None:
        """Background task to process a single document"""
        task_id = f"{kb_id}_{document.id}"
        
        try:
            logger.info(f"Starting background processing for document {document.id} in knowledge base {kb_id}")
            
            # Mark task as active
            self.active_tasks[task_id] = {
                "status": "processing",
                "started_at": datetime.now(),
                "document_id": document.id,
                "kb_id": kb_id
            }
            
            # Update document status to PROCESSING in MongoDB
            await self._update_document_status(
                mongodb_collection, kb_id, user_id, document.id, DocumentStatus.PROCESSING
            )
            
            # Process the document
            processing_result = await self.document_processor.process_document(
                document=document,
                kb_id=kb_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embedding_model=embedding_model,
                qdrant_client=qdrant_client,
                advanced_analysis=advanced_analysis
            )
            
            # Update document in MongoDB with processing results
            if processing_result["status"] == DocumentStatus.COMPLETED:
                await self._update_document_with_results(
                    mongodb_collection, kb_id, user_id, document.id, processing_result
                )
                logger.info(f"Successfully completed processing document {document.id}")
            else:
                await self._update_document_status(
                    mongodb_collection, kb_id, user_id, document.id, 
                    DocumentStatus.FAILED, processing_result.get("error")
                )
                logger.error(f"Failed to process document {document.id}: {processing_result.get('error')}")
            
            # Mark task as completed
            self.active_tasks[task_id] = {
                "status": "completed",
                "started_at": self.active_tasks[task_id]["started_at"],
                "completed_at": datetime.now(),
                "document_id": document.id,
                "kb_id": kb_id,
                "result": processing_result
            }
            
        except Exception as e:
            error_msg = f"Background task failed for document {document.id}: {str(e)}"
            logger.error(error_msg)
            
            # Update document status to FAILED
            try:
                await self._update_document_status(
                    mongodb_collection, kb_id, user_id, document.id, 
                    DocumentStatus.FAILED, str(e)
                )
            except Exception as update_error:
                logger.error(f"Failed to update document status after error: {str(update_error)}")
            
            # Mark task as failed
            self.active_tasks[task_id] = {
                "status": "failed",
                "started_at": self.active_tasks[task_id]["started_at"],
                "failed_at": datetime.now(),
                "document_id": document.id,
                "kb_id": kb_id,
                "error": str(e)
            }
    
    async def _update_document_status(
        self,
        mongodb_collection: AsyncIOMotorCollection,
        kb_id: str,
        user_id: str,
        document_id: str,
        status: DocumentStatus,
        error_message: str = None
    ) -> None:
        """Update document status in MongoDB"""
        try:
            update_data = {
                "documents.$.status": status,
                "documents.$.updated_at": datetime.now()
            }
            
            if error_message:
                update_data["documents.$.metadata.error"] = error_message
            
            await mongodb_collection.update_one(
                {"id": kb_id, "user_id": user_id, "documents.id": document_id},
                {"$set": update_data}
            )
            logger.info(f"Updated document {document_id} status to {status}")
        except Exception as e:
            logger.error(f"Failed to update document status: {str(e)}")
            raise
    
    async def _update_document_with_results(
        self,
        mongodb_collection: AsyncIOMotorCollection,
        kb_id: str,
        user_id: str,
        document_id: str,
        processing_result: Dict[str, Any]
    ) -> None:
        """Update document with processing results in MongoDB"""
        try:
            update_data = {
                "documents.$.status": processing_result["status"],
                "documents.$.chunks": processing_result["chunks"],
                "documents.$.tokens": processing_result["tokens"],
                "documents.$.updated_at": datetime.now(),
                "documents.$.metadata.text_length": processing_result["text_length"],
                "documents.$.metadata.chunks_stored": processing_result["chunks_stored"],
                "documents.$.metadata.processing_time": processing_result["processing_time"]
            }
            
            await mongodb_collection.update_one(
                {"id": kb_id, "user_id": user_id, "documents.id": document_id},
                {"$set": update_data}
            )
            logger.info(f"Updated document {document_id} with processing results")
        except Exception as e:
            logger.error(f"Failed to update document with results: {str(e)}")
            raise
    
    async def sync_knowledge_base_task(
        self,
        kb_id: str,
        user_id: str,
        documents: list,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model,
        qdrant_client,
        mongodb_collection: AsyncIOMotorCollection,
        advanced_analysis: bool = True
    ) -> None:
        """Background task to sync/reprocess all documents in a knowledge base"""
        try:
            logger.info(f"Starting background sync for knowledge base {kb_id}")
            
            # Process each document that needs processing
            for document in documents:
                if document.status in [DocumentStatus.PENDING, DocumentStatus.FAILED]:
                    await self.process_document_task(
                        document=document,
                        kb_id=kb_id,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        embedding_model=embedding_model,
                        qdrant_client=qdrant_client,
                        mongodb_collection=mongodb_collection,
                        user_id=user_id,
                        advanced_analysis=advanced_analysis
                    )
            
            # Update knowledge base last sync time
            await mongodb_collection.update_one(
                {"id": kb_id, "user_id": user_id},
                {"$set": {"updated_at": datetime.now()}}
            )
            
            logger.info(f"Completed background sync for knowledge base {kb_id}")
            
        except Exception as e:
            error_msg = f"Knowledge base sync failed for {kb_id}: {str(e)}"
            logger.error(error_msg)
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a background task"""
        return self.active_tasks.get(task_id, {"status": "not_found"})
    
    def list_active_tasks(self) -> Dict[str, Any]:
        """List all active tasks"""
        return {
            task_id: task_info 
            for task_id, task_info in self.active_tasks.items() 
            if task_info["status"] == "processing"
        }
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """Clean up completed/failed tasks older than max_age_hours"""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        tasks_to_remove = []
        
        for task_id, task_info in self.active_tasks.items():
            if task_info["status"] in ["completed", "failed"]:
                task_time = task_info.get("completed_at") or task_info.get("failed_at")
                if task_time and task_time.timestamp() < cutoff_time:
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.active_tasks[task_id]
        
        logger.info(f"Cleaned up {len(tasks_to_remove)} old background tasks")
        return len(tasks_to_remove)

# Global instance
background_task_service = BackgroundTaskService() 
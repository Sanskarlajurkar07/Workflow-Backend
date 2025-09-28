import os
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

# File processing imports
import PyPDF2
import docx
from bs4 import BeautifulSoup
import requests
import httpx

# Embedding imports
import openai
import cohere

# Qdrant imports
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

# Local imports
from models.knowledge_base import Document, DocumentStatus, EmbeddingModel, DataSourceType
from embedding_config import get_embedding_provider, get_model_name, get_max_tokens
from config import settings

logger = logging.getLogger("document_processor")

class DocumentProcessor:
    """Service for processing documents: extraction, chunking, embedding, and storage"""
    
    def __init__(self):
        self.openai_client = None
        self.cohere_client = None
        self._init_embedding_clients()
    
    def _init_embedding_clients(self):
        """Initialize embedding service clients"""
        try:
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            else:
                logger.warning("OpenAI API key not found")
                
            if settings.COHERE_API_KEY:
                self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
                logger.info("Cohere client initialized")
            else:
                logger.warning("Cohere API key not found")
        except Exception as e:
            logger.error(f"Failed to initialize embedding clients: {str(e)}")
    
    async def extract_text_from_file(self, file_path: str, content_type: str = None) -> str:
        """Extract text content from various file types"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                return await self._extract_from_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                return await self._extract_from_docx(file_path)
            elif file_extension == '.txt':
                return await self._extract_from_txt(file_path)
            else:
                # Try to read as plain text
                return await self._extract_from_txt(file_path)
                
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {str(e)}")
            raise Exception(f"Text extraction failed: {str(e)}")
    
    async def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF files"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {str(e)}")
            raise
        return text.strip()
    
    async def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX files"""
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            logger.error(f"DOCX extraction failed for {file_path}: {str(e)}")
            raise
        return text.strip()
    
    async def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                text = file.read()
        except Exception as e:
            logger.error(f"TXT extraction failed for {file_path}: {str(e)}")
            raise
        return text.strip()
    
    async def extract_text_from_url(self, url: str) -> str:
        """Extract text content from web URLs"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                # Parse HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                return text
                
        except Exception as e:
            logger.error(f"URL extraction failed for {url}: {str(e)}")
            raise Exception(f"URL extraction failed: {str(e)}")
    
    def chunk_text(self, text: str, chunk_size: int = 400, chunk_overlap: int = 0) -> List[str]:
        """Split text into chunks with optional overlap"""
        if not text.strip():
            return []
        
        # Simple word-based chunking
        words = text.split()
        chunks = []
        
        start_idx = 0
        while start_idx < len(words):
            end_idx = min(start_idx + chunk_size, len(words))
            chunk_words = words[start_idx:end_idx]
            chunk_text = ' '.join(chunk_words)
            chunks.append(chunk_text)
            
            if end_idx >= len(words):
                break
                
            # Move start position considering overlap
            start_idx = end_idx - chunk_overlap
        
        return chunks
    
    async def generate_embeddings(self, texts: List[str], embedding_model: EmbeddingModel) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        provider = get_embedding_provider(embedding_model)
        model_name = get_model_name(embedding_model)
        
        try:
            if provider == "openai":
                return await self._generate_openai_embeddings(texts, model_name)
            elif provider == "cohere":
                return await self._generate_cohere_embeddings(texts, model_name)
            else:
                raise Exception(f"Unsupported embedding provider: {provider}")
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            raise
    
    async def _generate_openai_embeddings(self, texts: List[str], model_name: str) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
        
        try:
            response = self.openai_client.embeddings.create(
                input=texts,
                model=model_name
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {str(e)}")
            raise
    
    async def _generate_cohere_embeddings(self, texts: List[str], model_name: str) -> List[List[float]]:
        """Generate embeddings using Cohere API"""
        if not self.cohere_client:
            raise Exception("Cohere client not initialized")
        
        try:
            response = self.cohere_client.embed(
                texts=texts,
                model=model_name,
                input_type="search_document"
            )
            return response.embeddings
        except Exception as e:
            logger.error(f"Cohere embedding generation failed: {str(e)}")
            raise
    
    async def store_embeddings_in_qdrant(
        self, 
        qdrant_client, 
        collection_name: str,
        chunks: List[str], 
        embeddings: List[List[float]], 
        document_id: str,
        document_name: str,
        metadata: Dict[str, Any] = None
    ) -> int:
        """Store text chunks and their embeddings in Qdrant"""
        try:
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_id = str(uuid.uuid4())
                payload = {
                    "document_id": document_id,
                    "document_name": document_name,
                    "chunk_index": i,
                    "text_chunk": chunk,
                    "chunk_length": len(chunk),
                    "created_at": datetime.now().isoformat()
                }
                
                # Add any additional metadata
                if metadata:
                    payload.update(metadata)
                
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
            
            # Batch upsert to Qdrant
            qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.info(f"Stored {len(points)} embeddings for document {document_id} in collection {collection_name}")
            return len(points)
            
        except Exception as e:
            logger.error(f"Failed to store embeddings in Qdrant: {str(e)}")
            raise
    
    async def process_document(
        self, 
        document: Document, 
        kb_id: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: EmbeddingModel,
        qdrant_client,
        advanced_analysis: bool = True
    ) -> Dict[str, Any]:
        """Complete document processing pipeline"""
        logger.info(f"Starting processing for document {document.id}: {document.name}")
        
        try:
            # Step 1: Extract text content
            if document.source_type == DataSourceType.FILE:
                text_content = await self.extract_text_from_file(
                    document.source_path, 
                    document.metadata.get('content_type')
                )
            elif document.source_type == DataSourceType.URL:
                text_content = await self.extract_text_from_url(document.source_path)
            else:
                raise Exception(f"Unsupported source type: {document.source_type}")
            
            if not text_content.strip():
                raise Exception("No text content extracted from document")
            
            # Step 2: Chunk the text
            chunks = self.chunk_text(text_content, chunk_size, chunk_overlap)
            if not chunks:
                raise Exception("No chunks generated from text content")
            
            # Step 3: Generate embeddings
            embeddings = await self.generate_embeddings(chunks, embedding_model)
            
            # Step 4: Store in Qdrant
            chunks_stored = await self.store_embeddings_in_qdrant(
                qdrant_client=qdrant_client,
                collection_name=kb_id,
                chunks=chunks,
                embeddings=embeddings,
                document_id=document.id,
                document_name=document.name,
                metadata=document.metadata
            )
            
            # Calculate token count (rough estimation)
            total_tokens = sum(len(chunk.split()) for chunk in chunks)
            
            result = {
                "status": DocumentStatus.COMPLETED,
                "chunks": len(chunks),
                "tokens": total_tokens,
                "text_length": len(text_content),
                "chunks_stored": chunks_stored,
                "processing_time": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully processed document {document.id}: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Document processing failed for {document.id}: {str(e)}"
            logger.error(error_msg)
            return {
                "status": DocumentStatus.FAILED,
                "error": str(e),
                "processing_time": datetime.now().isoformat()
            }
    
    async def extract_sample_text(self, file_path: str, max_chars: int = 2000) -> str:
        """Extract a sample of text from document for analysis"""
        try:
            # Determine file type and extract text
            full_text = await self.extract_text_from_file(file_path)
            
            # Return sample of specified length
            if len(full_text) <= max_chars:
                return full_text
            else:
                # Try to break at word boundary
                sample = full_text[:max_chars]
                last_space = sample.rfind(' ')
                if last_space > max_chars * 0.8:  # If we can find a space in the last 20%
                    sample = sample[:last_space]
                
                return sample
                
        except Exception as e:
            logger.error(f"Failed to extract sample text from {file_path}: {str(e)}")
            return f"Error extracting sample: {str(e)}"
    
    async def process_document_smart(self, 
                                   document_path: str, 
                                   processing_strategy: Dict[str, Any]) -> List[str]:
        """Process document with smart strategy-based optimizations"""
        try:
            # Extract text using appropriate method
            if document_path.startswith('http'):
                text = await self.extract_text_from_url(document_path)
            else:
                text = await self.extract_text_from_file(document_path)
            
            if not text.strip():
                logger.warning(f"No text extracted from {document_path}")
                return []
            
            # Apply smart chunking based on strategy
            chunk_size = processing_strategy.get("chunk_size", 400)
            overlap = processing_strategy.get("overlap", 50)
            
            # Adjust parameters based on document type and confidence
            confidence = processing_strategy.get("confidence", 0.5)
            if confidence > 0.7:
                # High confidence in strategy, use as-is
                chunks = self.chunk_text(text, chunk_size, overlap)
            else:
                # Lower confidence, use more conservative chunking
                conservative_size = max(300, int(chunk_size * 0.8))
                conservative_overlap = min(overlap, conservative_size // 4)
                chunks = self.chunk_text(text, conservative_size, conservative_overlap)
            
            # Filter out very short chunks (less than 50 characters)
            filtered_chunks = [chunk for chunk in chunks if len(chunk.strip()) >= 50]
            
            logger.info(f"Processed {document_path} into {len(filtered_chunks)} chunks using smart strategy")
            return filtered_chunks
            
        except Exception as e:
            logger.error(f"Smart document processing failed for {document_path}: {str(e)}")
            raise 
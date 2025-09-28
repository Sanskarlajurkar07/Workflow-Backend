import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Embedding imports
import openai
import cohere

# Local imports
from models.knowledge_base import EmbeddingModel, KnowledgeBase
from embedding_config import get_embedding_provider, get_model_name
from config import settings

logger = logging.getLogger("search_service")

class SearchResult:
    """Search result data structure"""
    def __init__(self, text: str, score: float, source: str, document_id: str, metadata: Dict[str, Any] = None):
        self.text = text
        self.score = score
        self.source = source
        self.document_id = document_id
        self.metadata = metadata or {}

class SearchService:
    """Service for semantic search using Qdrant and embeddings"""
    
    def __init__(self):
        self.openai_client = None
        self.cohere_client = None
        self._init_embedding_clients()
    
    def _init_embedding_clients(self):
        """Initialize embedding service clients"""
        try:
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("Search service: OpenAI client initialized")
            else:
                logger.warning("Search service: OpenAI API key not found")
                
            if settings.COHERE_API_KEY:
                self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
                logger.info("Search service: Cohere client initialized")
            else:
                logger.warning("Search service: Cohere API key not found")
        except Exception as e:
            logger.error(f"Failed to initialize search embedding clients: {str(e)}")
    
    async def generate_query_embedding(self, query: str, embedding_model: EmbeddingModel) -> List[float]:
        """Generate embedding for search query"""
        provider = get_embedding_provider(embedding_model)
        model_name = get_model_name(embedding_model)
        
        try:
            if provider == "openai":
                return await self._generate_openai_query_embedding(query, model_name)
            elif provider == "cohere":
                return await self._generate_cohere_query_embedding(query, model_name)
            else:
                raise Exception(f"Unsupported embedding provider: {provider}")
        except Exception as e:
            logger.error(f"Query embedding generation failed: {str(e)}")
            raise
    
    async def _generate_openai_query_embedding(self, query: str, model_name: str) -> List[float]:
        """Generate query embedding using OpenAI API"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
        
        try:
            response = self.openai_client.embeddings.create(
                input=[query],
                model=model_name
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI query embedding generation failed: {str(e)}")
            raise
    
    async def _generate_cohere_query_embedding(self, query: str, model_name: str) -> List[float]:
        """Generate query embedding using Cohere API"""
        if not self.cohere_client:
            raise Exception("Cohere client not initialized")
        
        try:
            response = self.cohere_client.embed(
                texts=[query],
                model=model_name,
                input_type="search_query"  # Different input type for search queries
            )
            return response.embeddings[0]
        except Exception as e:
            logger.error(f"Cohere query embedding generation failed: {str(e)}")
            raise
    
    async def search_knowledge_base(
        self,
        qdrant_client,
        kb: KnowledgeBase,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> List[SearchResult]:
        """Perform semantic search in a knowledge base"""
        logger.info(f"Searching knowledge base {kb.id} with query: '{query}' (top_k={top_k})")
        
        try:
            # Generate embedding for the search query
            query_embedding = await self.generate_query_embedding(query, kb.embedding_model)
            
            # Perform similarity search in Qdrant
            search_results = qdrant_client.search(
                collection_name=kb.id,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False  # We don't need the vectors back
            )
            
            # Convert Qdrant results to SearchResult objects
            results = []
            for result in search_results:
                payload = result.payload
                search_result = SearchResult(
                    text=payload.get("text_chunk", ""),
                    score=result.score,
                    source=payload.get("document_name", "Unknown"),
                    document_id=payload.get("document_id", ""),
                    metadata={
                        "chunk_index": payload.get("chunk_index", 0),
                        "chunk_length": payload.get("chunk_length", 0),
                        "created_at": payload.get("created_at", ""),
                        "original_filename": payload.get("original_filename", ""),
                        "content_type": payload.get("content_type", "")
                    }
                )
                results.append(search_result)
            
            logger.info(f"Found {len(results)} results for query in knowledge base {kb.id}")
            return results
            
        except Exception as e:
            logger.error(f"Search failed for knowledge base {kb.id}: {str(e)}")
            raise Exception(f"Search failed: {str(e)}")
    
    def format_search_results(self, results: List[SearchResult], query: str) -> Dict[str, Any]:
        """Format search results for API response"""
        formatted_results = []
        
        for result in results:
            formatted_result = {
                "text": result.text,
                "score": round(result.score, 4),
                "source": result.source,
                "document_id": result.document_id,
                "metadata": result.metadata
            }
            formatted_results.append(formatted_result)
        
        return {
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "search_time": datetime.now().isoformat()
        }
    
    async def search_with_filters(
        self,
        qdrant_client,
        kb: KnowledgeBase,
        query: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> List[SearchResult]:
        """Perform search with optional document filtering"""
        logger.info(f"Searching knowledge base {kb.id} with filters: document_ids={document_ids}")
        
        try:
            # Generate embedding for the search query
            query_embedding = await self.generate_query_embedding(query, kb.embedding_model)
            
            # Build filter conditions
            search_filter = None
            if document_ids:
                from qdrant_client.models import Filter, FieldCondition, MatchAny
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchAny(any=document_ids)
                        )
                    ]
                )
            
            # Perform similarity search in Qdrant with filters
            search_results = qdrant_client.search(
                collection_name=kb.id,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            # Convert results to SearchResult objects
            results = []
            for result in search_results:
                payload = result.payload
                search_result = SearchResult(
                    text=payload.get("text_chunk", ""),
                    score=result.score,
                    source=payload.get("document_name", "Unknown"),
                    document_id=payload.get("document_id", ""),
                    metadata={
                        "chunk_index": payload.get("chunk_index", 0),
                        "chunk_length": payload.get("chunk_length", 0),
                        "created_at": payload.get("created_at", ""),
                        "original_filename": payload.get("original_filename", ""),
                        "content_type": payload.get("content_type", "")
                    }
                )
                results.append(search_result)
            
            logger.info(f"Found {len(results)} filtered results for query in knowledge base {kb.id}")
            return results
            
        except Exception as e:
            logger.error(f"Filtered search failed for knowledge base {kb.id}: {str(e)}")
            raise Exception(f"Filtered search failed: {str(e)}")
    
    async def generate_embedding(self, text: str, embedding_model: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            # Convert string model name to enum if needed
            if isinstance(embedding_model, str):
                # Map common model names to our enum values
                model_mapping = {
                    "text-embedding-3-small": EmbeddingModel.TEXT_EMBEDDING_3_SMALL,
                    "text-embedding-3-large": EmbeddingModel.TEXT_EMBEDDING_3_LARGE,
                    "text-embedding-ada-002": EmbeddingModel.TEXT_EMBEDDING_ADA_002,
                    "embed-english-v3.0": EmbeddingModel.COHERE_EMBED_ENGLISH_V3,
                    "embed-multilingual-v3.0": EmbeddingModel.COHERE_EMBED_MULTILINGUAL_V3
                }
                embedding_model_enum = model_mapping.get(embedding_model, EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
            else:
                embedding_model_enum = embedding_model
            
            return await self.generate_query_embedding(text, embedding_model_enum)
        except Exception as e:
            logger.error(f"Single embedding generation failed: {str(e)}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str], embedding_model: str) -> List[List[float]]:
        """Generate embeddings for a batch of texts"""
        try:
            # Convert string model name to enum if needed
            if isinstance(embedding_model, str):
                model_mapping = {
                    "text-embedding-3-small": EmbeddingModel.TEXT_EMBEDDING_3_SMALL,
                    "text-embedding-3-large": EmbeddingModel.TEXT_EMBEDDING_3_LARGE,
                    "text-embedding-ada-002": EmbeddingModel.TEXT_EMBEDDING_ADA_002,
                    "embed-english-v3.0": EmbeddingModel.COHERE_EMBED_ENGLISH_V3,
                    "embed-multilingual-v3.0": EmbeddingModel.COHERE_EMBED_MULTILINGUAL_V3
                }
                embedding_model_enum = model_mapping.get(embedding_model, EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
            else:
                embedding_model_enum = embedding_model
            
            provider = get_embedding_provider(embedding_model_enum)
            model_name = get_model_name(embedding_model_enum)
            
            if provider == "openai":
                return await self._generate_openai_embeddings_batch(texts, model_name)
            elif provider == "cohere":
                return await self._generate_cohere_embeddings_batch(texts, model_name)
            else:
                raise Exception(f"Unsupported embedding provider: {provider}")
                
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {str(e)}")
            raise
    
    async def _generate_openai_embeddings_batch(self, texts: List[str], model_name: str) -> List[List[float]]:
        """Generate batch embeddings using OpenAI API"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
        
        try:
            response = self.openai_client.embeddings.create(
                input=texts,
                model=model_name
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"OpenAI batch embedding generation failed: {str(e)}")
            raise
    
    async def _generate_cohere_embeddings_batch(self, texts: List[str], model_name: str) -> List[List[float]]:
        """Generate batch embeddings using Cohere API"""
        if not self.cohere_client:
            raise Exception("Cohere client not initialized")
        
        try:
            response = self.cohere_client.embed(
                texts=texts,
                model=model_name,
                input_type="search_document"  # For document embeddings
            )
            return response.embeddings
        except Exception as e:
            logger.error(f"Cohere batch embedding generation failed: {str(e)}")
            raise 
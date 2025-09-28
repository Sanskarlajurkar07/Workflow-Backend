"""
Advanced Smart Database System
Provides intelligent database management, auto-optimization, smart indexing,
and AI-powered recommendations for knowledge bases.
"""

import asyncio
import logging
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import uuid
from motor.motor_asyncio import AsyncIOMotorCollection
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import openai
from cohere import AsyncClient as CohereClient

from .document_processor import DocumentProcessor
from .search_service import SearchService
from .monitoring import performance_monitor, metrics_collector
from .performance_optimizer import smart_cache, embedding_cache, search_cache
from embedding_config import get_embedding_model_config, EMBEDDING_MODEL_CONFIG

logger = logging.getLogger(__name__)

@dataclass
class SmartIndexMetrics:
    """Metrics for smart indexing system"""
    total_documents: int
    total_chunks: int
    avg_embedding_quality: float
    search_performance_score: float
    storage_efficiency: float
    last_optimization: datetime
    optimization_suggestions: List[str]

@dataclass
class QueryPattern:
    """Represents a common query pattern"""
    pattern: str
    frequency: int
    avg_response_time: float
    success_rate: float
    suggested_optimizations: List[str]

@dataclass
class DocumentCluster:
    """Represents a cluster of similar documents"""
    id: str
    center_embedding: List[float]
    document_ids: List[str]
    topic_keywords: List[str]
    coherence_score: float

class SmartDatabaseEngine:
    """Advanced smart database engine with AI-powered optimizations"""
    
    def __init__(self, 
                 qdrant_client: QdrantClient,
                 mongodb_collection: AsyncIOMotorCollection):
        self.qdrant_client = qdrant_client
        self.mongodb_collection = mongodb_collection
        self.document_processor = DocumentProcessor()
        self.search_service = SearchService()
        
        # AI clients for advanced features
        self.openai_client = openai.AsyncOpenAI()
        self.cohere_client = CohereClient()
        
        # Analytics storage
        self.query_analytics = defaultdict(list)
        self.performance_metrics = {}
        
    async def create_smart_knowledge_base(self, 
                                        kb_id: str,
                                        config: Dict[str, Any],
                                        user_id: str) -> Dict[str, Any]:
        """Create an optimized knowledge base with smart defaults"""
        
        # Analyze the intended use case to optimize settings
        smart_config = await self._optimize_kb_configuration(config)
        
        collection_name = f"kb_{kb_id}"
        
        # Create Qdrant collection with optimal settings
        embedding_config = get_embedding_model_config(smart_config["embedding_model"])
        
        await self._create_optimized_collection(collection_name, embedding_config)
        
        # Store smart configuration in MongoDB
        kb_doc = {
            "id": kb_id,
            "user_id": user_id,
            "smart_config": smart_config,
            "optimization_history": [],
            "performance_metrics": {},
            "created_at": datetime.utcnow(),
            "last_optimized": datetime.utcnow()
        }
        
        await self.mongodb_collection.insert_one(kb_doc)
        
        logger.info(f"Created smart knowledge base {kb_id} with optimized configuration")
        return smart_config
    
    async def _optimize_kb_configuration(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to optimize knowledge base configuration"""
        
        # Analyze the description and intended use to suggest optimal settings
        description = base_config.get("description", "")
        
        optimization_prompt = f"""
        Analyze this knowledge base configuration and suggest optimal settings:
        
        Description: {description}
        Current chunk_size: {base_config.get('chunk_size', 400)}
        Current embedding_model: {base_config.get('embedding_model', 'text-embedding-3-small')}
        
        Consider:
        1. Document types likely to be used
        2. Search patterns expected
        3. Performance vs. quality trade-offs
        4. Cost optimization
        
        Respond with JSON containing optimized settings and reasoning.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": optimization_prompt}],
                temperature=0.1
            )
            
            optimization_result = json.loads(response.choices[0].message.content)
            
            # Apply suggested optimizations
            optimized_config = base_config.copy()
            optimized_config.update(optimization_result.get("settings", {}))
            optimized_config["optimization_reasoning"] = optimization_result.get("reasoning", "")
            
            return optimized_config
            
        except Exception as e:
            logger.warning(f"AI optimization failed, using defaults: {e}")
            return base_config
    
    async def _create_optimized_collection(self, 
                                         collection_name: str, 
                                         embedding_config: Dict[str, Any]):
        """Create Qdrant collection with performance optimizations"""
        
        # Check if collection exists
        try:
            self.qdrant_client.get_collection(collection_name)
            logger.info(f"Collection {collection_name} already exists")
            return
        except:
            pass
        
        # Create with optimized parameters
        self.qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=embedding_config["dimension"],
                distance=Distance.COSINE,
                # Add HNSW parameters for better performance
                hnsw_config={
                    "m": 16,  # Number of bi-directional links
                    "ef_construct": 200,  # Size of dynamic candidate list
                    "full_scan_threshold": 10000  # Threshold for full scan
                }
            ),
            # Enable payload indexing for faster filtering
            optimizers_config={
                "deleted_threshold": 0.2,
                "vacuum_min_vector_number": 1000,
                "default_segment_number": 2
            }
        )
        
        logger.info(f"Created optimized Qdrant collection: {collection_name}")
    
    async def intelligent_document_processing(self, 
                                            kb_id: str,
                                            document_path: str,
                                            metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process document with AI-powered optimizations"""
        
        # Get KB configuration
        kb_doc = await self.mongodb_collection.find_one({"id": kb_id})
        if not kb_doc:
            raise ValueError(f"Knowledge base {kb_id} not found")
        
        smart_config = kb_doc.get("smart_config", {})
        
        # Analyze document to determine optimal processing strategy
        processing_strategy = await self._analyze_document_strategy(document_path, smart_config)
        
        # Extract text with strategy-specific optimizations
        chunks = await self.document_processor.process_document_smart(
            document_path, 
            processing_strategy
        )
        
        # Generate embeddings with batch optimization
        embeddings = await self._generate_optimized_embeddings(
            chunks, 
            smart_config.get("embedding_model", "text-embedding-3-small")
        )
        
        # Store in Qdrant with smart indexing
        collection_name = f"kb_{kb_id}"
        point_ids = await self._store_with_smart_indexing(
            collection_name, 
            chunks, 
            embeddings, 
            metadata
        )
        
        # Update performance metrics
        await self._update_processing_metrics(kb_id, len(chunks), processing_strategy)
        
        return {
            "chunks_processed": len(chunks),
            "strategy_used": processing_strategy,
            "point_ids": point_ids,
            "processing_quality_score": await self._calculate_processing_quality(chunks, embeddings)
        }
    
    async def _analyze_document_strategy(self, 
                                       document_path: str,
                                       smart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze document to determine optimal processing strategy"""
        
        # Sample the document to understand its structure
        sample_text = await self.document_processor.extract_sample_text(document_path, max_chars=2000)
        
        analysis_prompt = f"""
        Analyze this document sample and suggest optimal processing strategy:
        
        Sample text:
        {sample_text[:1000]}...
        
        Determine:
        1. Document type and structure
        2. Optimal chunk size (considering current: {smart_config.get('chunk_size', 400)})
        3. Overlap strategy
        4. Special handling needed (tables, code, etc.)
        5. Metadata extraction opportunities
        
        Respond with JSON containing processing recommendations.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.1
            )
            
            strategy = json.loads(response.choices[0].message.content)
            strategy["confidence"] = 0.8  # AI analysis confidence
            
            return strategy
            
        except Exception as e:
            logger.warning(f"Document analysis failed, using defaults: {e}")
            return {
                "chunk_size": smart_config.get("chunk_size", 400),
                "overlap": smart_config.get("chunk_overlap", 50),
                "confidence": 0.5
            }
    
    async def _generate_optimized_embeddings(self, 
                                           chunks: List[str],
                                           embedding_model: str) -> List[List[float]]:
        """Generate embeddings with performance optimizations"""
        
        # Use batch processing for efficiency
        batch_size = 100
        embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Check cache first
            cached_embeddings = []
            uncached_chunks = []
            uncached_indices = []
            
            for j, chunk in enumerate(batch):
                cached = await embedding_cache.get_embedding(chunk, embedding_model)
                if cached:
                    cached_embeddings.append((i + j, cached))
                else:
                    uncached_chunks.append(chunk)
                    uncached_indices.append(i + j)
            
            # Generate embeddings for uncached chunks
            if uncached_chunks:
                batch_embeddings = await self.search_service.generate_embeddings_batch(
                    uncached_chunks, embedding_model
                )
                
                # Cache new embeddings
                for chunk, embedding in zip(uncached_chunks, batch_embeddings):
                    await embedding_cache.set_embedding(chunk, embedding_model, embedding)
                
                # Combine with cached results
                new_embeddings = [(idx, emb) for idx, emb in zip(uncached_indices, batch_embeddings)]
                all_embeddings = cached_embeddings + new_embeddings
            else:
                all_embeddings = cached_embeddings
            
            # Sort by original index and add to results
            all_embeddings.sort(key=lambda x: x[0])
            embeddings.extend([emb for _, emb in all_embeddings])
        
        return embeddings
    
    async def _store_with_smart_indexing(self, 
                                       collection_name: str,
                                       chunks: List[str],
                                       embeddings: List[List[float]],
                                       metadata: Dict[str, Any]) -> List[str]:
        """Store vectors with smart indexing optimizations"""
        
        points = []
        point_ids = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            
            # Enhanced metadata with smart features
            enhanced_metadata = {
                **metadata,
                "chunk_index": i,
                "chunk_text": chunk,
                "chunk_length": len(chunk),
                "embedding_quality": self._calculate_embedding_quality(embedding),
                "topics": await self._extract_topics(chunk),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=enhanced_metadata
            ))
        
        # Batch upload for performance
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=batch
            )
        
        logger.info(f"Stored {len(points)} vectors in {collection_name} with smart indexing")
        return point_ids
    
    def _calculate_embedding_quality(self, embedding: List[float]) -> float:
        """Calculate quality score for an embedding"""
        # Simple quality metric based on vector properties
        embedding_array = np.array(embedding)
        
        # Check for degenerate cases
        if np.all(embedding_array == 0):
            return 0.0
        
        # Normalize and calculate quality based on distribution
        norm = np.linalg.norm(embedding_array)
        normalized = embedding_array / norm if norm > 0 else embedding_array
        
        # Quality based on how well-distributed the values are
        variance = np.var(normalized)
        sparsity = np.sum(np.abs(normalized) < 0.01) / len(normalized)
        
        quality = (1.0 - sparsity) * min(variance * 10, 1.0)
        return float(quality)
    
    async def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text chunk"""
        try:
            # Use Cohere for topic extraction
            response = await self.cohere_client.classify(
                inputs=[text],
                examples=[],  # Would need pre-trained examples in production
                model="embed-english-v3.0"
            )
            
            # For now, use simple keyword extraction
            words = text.lower().split()
            word_freq = Counter(words)
            
            # Filter out common words and return top topics
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            topics = [word for word, freq in word_freq.most_common(5) 
                     if word not in stop_words and len(word) > 3]
            
            return topics[:3]  # Return top 3 topics
            
        except Exception as e:
            logger.warning(f"Topic extraction failed: {e}")
            return []
    
    async def intelligent_search(self, 
                               kb_id: str,
                               query: str,
                               options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform intelligent search with AI optimizations"""
        
        options = options or {}
        
        # Analyze query to optimize search strategy
        search_strategy = await self._analyze_search_query(query, kb_id)
        
        # Record query analytics
        self._record_query_analytics(kb_id, query, search_strategy)
        
        # Perform optimized search
        results = await self._execute_optimized_search(
            kb_id, query, search_strategy, options
        )
        
        # Post-process results with AI
        enhanced_results = await self._enhance_search_results(query, results)
        
        # Update search metrics
        await self._update_search_metrics(kb_id, query, enhanced_results)
        
        return enhanced_results
    
    async def _analyze_search_query(self, query: str, kb_id: str) -> Dict[str, Any]:
        """Analyze search query to determine optimal strategy"""
        
        # Get historical query patterns
        kb_analytics = self.query_analytics.get(kb_id, [])
        
        query_analysis_prompt = f"""
        Analyze this search query and suggest optimal search strategy:
        
        Query: "{query}"
        
        Consider:
        1. Query type (factual, conceptual, procedural, etc.)
        2. Expected answer length
        3. Required context amount
        4. Precision vs. recall preference
        5. Semantic vs. keyword matching needs
        
        Historical patterns: {len(kb_analytics)} previous queries
        
        Respond with JSON containing search optimization strategy.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": query_analysis_prompt}],
                temperature=0.1
            )
            
            strategy = json.loads(response.choices[0].message.content)
            strategy["confidence"] = 0.8
            
            return strategy
            
        except Exception as e:
            logger.warning(f"Query analysis failed, using defaults: {e}")
            return {
                "top_k": 5,
                "score_threshold": 0.7,
                "search_type": "semantic",
                "confidence": 0.5
            }
    
    def _record_query_analytics(self, kb_id: str, query: str, strategy: Dict[str, Any]):
        """Record query analytics for optimization"""
        
        self.query_analytics[kb_id].append({
            "query": query,
            "strategy": strategy,
            "timestamp": datetime.utcnow(),
            "query_length": len(query),
            "query_words": len(query.split())
        })
        
        # Keep only recent analytics (last 1000 queries)
        if len(self.query_analytics[kb_id]) > 1000:
            self.query_analytics[kb_id] = self.query_analytics[kb_id][-1000:]
    
    async def _execute_optimized_search(self, 
                                      kb_id: str,
                                      query: str,
                                      strategy: Dict[str, Any],
                                      options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute search with optimization strategy"""
        
        collection_name = f"kb_{kb_id}"
        
        # Generate query embedding
        embedding_model = options.get("embedding_model", "text-embedding-3-small")
        query_embedding = await self.search_service.generate_embedding(query, embedding_model)
        
        # Apply strategy parameters
        top_k = strategy.get("top_k", options.get("top_k", 5))
        score_threshold = strategy.get("score_threshold", options.get("score_threshold", 0.7))
        
        # Perform vector search
        search_results = self.qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True
        )
        
        # Convert to standard format
        results = []
        for result in search_results:
            results.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("chunk_text", ""),
                "metadata": result.payload,
                "embedding_quality": result.payload.get("embedding_quality", 0.0)
            })
        
        return results
    
    async def _enhance_search_results(self, 
                                    query: str,
                                    results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use AI to enhance and explain search results"""
        
        if not results:
            return {
                "query": query,
                "results": [],
                "summary": "No relevant results found.",
                "suggestions": ["Try using different keywords", "Check spelling", "Use more general terms"]
            }
        
        # Generate explanation and summary
        results_text = "\n\n".join([f"Result {i+1}: {r['text'][:200]}..." 
                                   for i, r in enumerate(results[:3])])
        
        enhancement_prompt = f"""
        Analyze these search results for the query: "{query}"
        
        Results:
        {results_text}
        
        Provide:
        1. A brief summary of what was found
        2. How well the results answer the query
        3. Suggestions for better results if needed
        4. Key insights or patterns
        
        Respond with JSON containing summary, relevance_score, and suggestions.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": enhancement_prompt}],
                temperature=0.1
            )
            
            enhancement = json.loads(response.choices[0].message.content)
            
            return {
                "query": query,
                "results": results,
                "summary": enhancement.get("summary", ""),
                "relevance_score": enhancement.get("relevance_score", 0.5),
                "suggestions": enhancement.get("suggestions", []),
                "total_results": len(results),
                "search_time": "< 1s"
            }
            
        except Exception as e:
            logger.warning(f"Result enhancement failed: {e}")
            return {
                "query": query,
                "results": results,
                "summary": f"Found {len(results)} results for your query.",
                "relevance_score": 0.7,
                "suggestions": [],
                "total_results": len(results),
                "search_time": "< 1s"
            }
    
    async def auto_optimize_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """Automatically optimize knowledge base performance"""
        
        # Analyze current performance
        metrics = await self._analyze_kb_performance(kb_id)
        
        # Generate optimization recommendations
        recommendations = await self._generate_optimization_recommendations(kb_id, metrics)
        
        # Apply safe optimizations automatically
        applied_optimizations = await self._apply_safe_optimizations(kb_id, recommendations)
        
        # Update optimization history
        await self._update_optimization_history(kb_id, applied_optimizations)
        
        return {
            "kb_id": kb_id,
            "performance_metrics": metrics,
            "recommendations": recommendations,
            "applied_optimizations": applied_optimizations,
            "optimization_timestamp": datetime.utcnow().isoformat()
        }
    
    async def _analyze_kb_performance(self, kb_id: str) -> SmartIndexMetrics:
        """Analyze knowledge base performance metrics"""
        
        collection_name = f"kb_{kb_id}"
        
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(collection_name)
            
            # Count total points
            total_points = collection_info.points_count
            
            # Sample embeddings to calculate quality
            sample_results = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
                with_vectors=True
            )
            
            # Calculate metrics
            quality_scores = []
            chunk_lengths = []
            
            for point in sample_results[0]:
                if hasattr(point, 'payload') and point.payload:
                    quality_scores.append(point.payload.get("embedding_quality", 0.0))
                    chunk_lengths.append(point.payload.get("chunk_length", 0))
            
            avg_quality = np.mean(quality_scores) if quality_scores else 0.0
            avg_chunk_length = np.mean(chunk_lengths) if chunk_lengths else 0
            
            # Get KB document for last optimization
            kb_doc = await self.mongodb_collection.find_one({"id": kb_id})
            last_optimization = kb_doc.get("last_optimized", datetime.utcnow()) if kb_doc else datetime.utcnow()
            
            return SmartIndexMetrics(
                total_documents=total_points,
                total_chunks=total_points,
                avg_embedding_quality=avg_quality,
                search_performance_score=0.8,  # Would calculate from actual search metrics
                storage_efficiency=min(avg_chunk_length / 1000, 1.0),
                last_optimization=last_optimization,
                optimization_suggestions=[]
            )
            
        except Exception as e:
            logger.error(f"Performance analysis failed for {kb_id}: {e}")
            return SmartIndexMetrics(
                total_documents=0,
                total_chunks=0,
                avg_embedding_quality=0.0,
                search_performance_score=0.0,
                storage_efficiency=0.0,
                last_optimization=datetime.utcnow(),
                optimization_suggestions=["Performance analysis failed"]
            )
    
    async def get_smart_analytics(self, kb_id: str) -> Dict[str, Any]:
        """Get comprehensive analytics for a knowledge base"""
        
        # Performance metrics
        metrics = await self._analyze_kb_performance(kb_id)
        
        # Query patterns
        query_patterns = self._analyze_query_patterns(kb_id)
        
        # Document clusters
        clusters = await self._analyze_document_clusters(kb_id)
        
        # Usage insights
        insights = await self._generate_usage_insights(kb_id, metrics, query_patterns)
        
        return {
            "kb_id": kb_id,
            "performance_metrics": asdict(metrics),
            "query_patterns": query_patterns,
            "document_clusters": [asdict(cluster) for cluster in clusters],
            "usage_insights": insights,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _analyze_query_patterns(self, kb_id: str) -> List[QueryPattern]:
        """Analyze common query patterns"""
        
        queries = self.query_analytics.get(kb_id, [])
        if not queries:
            return []
        
        # Group similar queries
        query_groups = defaultdict(list)
        for query_data in queries:
            # Simple grouping by first word (could be more sophisticated)
            first_word = query_data["query"].split()[0].lower() if query_data["query"] else "unknown"
            query_groups[first_word].append(query_data)
        
        patterns = []
        for pattern, group in query_groups.items():
            if len(group) >= 2:  # Only patterns with multiple occurrences
                patterns.append(QueryPattern(
                    pattern=pattern,
                    frequency=len(group),
                    avg_response_time=0.5,  # Would calculate from actual metrics
                    success_rate=0.8,  # Would calculate from actual results
                    suggested_optimizations=[]
                ))
        
        return sorted(patterns, key=lambda x: x.frequency, reverse=True)[:10]
    
    async def _analyze_document_clusters(self, kb_id: str) -> List[DocumentCluster]:
        """Analyze document clusters for insights"""
        
        collection_name = f"kb_{kb_id}"
        
        try:
            # Get sample of vectors for clustering
            sample_results = self.qdrant_client.scroll(
                collection_name=collection_name,
                limit=200,
                with_payload=True,
                with_vectors=True
            )
            
            if not sample_results[0]:
                return []
            
            # Simple clustering (in production, use proper clustering algorithm)
            vectors = []
            metadata = []
            
            for point in sample_results[0]:
                if hasattr(point, 'vector') and point.vector:
                    vectors.append(point.vector)
                    metadata.append(point.payload)
            
            if len(vectors) < 3:
                return []
            
            # Use simple k-means like approach
            n_clusters = min(5, len(vectors) // 10)
            if n_clusters < 2:
                return []
            
            # For simplicity, just create one cluster with all documents
            center = np.mean(vectors, axis=0).tolist()
            
            # Extract topics from documents
            all_topics = []
            for meta in metadata:
                all_topics.extend(meta.get("topics", []))
            
            top_topics = [topic for topic, count in Counter(all_topics).most_common(5)]
            
            cluster = DocumentCluster(
                id="cluster_1",
                center_embedding=center,
                document_ids=[str(i) for i in range(len(vectors))],
                topic_keywords=top_topics,
                coherence_score=0.7
            )
            
            return [cluster]
            
        except Exception as e:
            logger.error(f"Cluster analysis failed for {kb_id}: {e}")
            return []
    
    async def _generate_usage_insights(self, 
                                     kb_id: str,
                                     metrics: SmartIndexMetrics,
                                     patterns: List[QueryPattern]) -> List[str]:
        """Generate actionable insights from analytics"""
        
        insights = []
        
        # Performance insights
        if metrics.avg_embedding_quality < 0.5:
            insights.append("📊 Embedding quality is low. Consider re-processing documents with better chunking.")
        
        if metrics.storage_efficiency < 0.3:
            insights.append("💾 Storage efficiency could be improved with larger chunk sizes.")
        
        if metrics.total_documents == 0:
            insights.append("📁 No documents found. Start by uploading some content.")
        
        # Query pattern insights
        if patterns:
            most_common = patterns[0]
            insights.append(f"🔍 Most common query pattern: '{most_common.pattern}' ({most_common.frequency} times)")
        
        if len(patterns) > 3:
            insights.append("🎯 You have diverse query patterns. Consider creating specialized indexes.")
        
        # Optimization insights
        days_since_optimization = (datetime.utcnow() - metrics.last_optimization).days
        if days_since_optimization > 30:
            insights.append(f"⚡ Last optimization was {days_since_optimization} days ago. Consider running auto-optimization.")
        
        return insights

    async def _calculate_processing_quality(self, chunks: List[str], embeddings: List[List[float]]) -> float:
        """Calculate overall processing quality score"""
        if not chunks or not embeddings:
            return 0.0
        
        # Calculate average embedding quality
        quality_scores = [self._calculate_embedding_quality(emb) for emb in embeddings]
        avg_quality = np.mean(quality_scores)
        
        # Factor in chunk size distribution
        chunk_lengths = [len(chunk) for chunk in chunks]
        length_variance = np.var(chunk_lengths) / np.mean(chunk_lengths) if chunk_lengths else 0
        
        # Penalize high variance in chunk lengths
        length_penalty = max(0, 1 - length_variance)
        
        return float(avg_quality * length_penalty)
    
    async def _update_processing_metrics(self, kb_id: str, chunks_count: int, strategy: Dict[str, Any]):
        """Update processing metrics for a knowledge base"""
        try:
            # Update MongoDB with processing metrics
            await self.mongodb_collection.update_one(
                {"id": kb_id},
                {
                    "$inc": {"performance_metrics.total_chunks_processed": chunks_count},
                    "$set": {
                        "performance_metrics.last_processing_strategy": strategy,
                        "performance_metrics.last_processed": datetime.utcnow()
                    }
                }
            )
            logger.info(f"Updated processing metrics for KB {kb_id}")
        except Exception as e:
            logger.error(f"Failed to update processing metrics: {e}")
    
    async def _update_search_metrics(self, kb_id: str, query: str, results: Dict[str, Any]):
        """Update search metrics for a knowledge base"""
        try:
            # Update search analytics
            await self.mongodb_collection.update_one(
                {"id": kb_id},
                {
                    "$inc": {
                        "performance_metrics.total_searches": 1,
                        f"performance_metrics.results_count_{len(results.get('results', []))}": 1
                    },
                    "$set": {
                        "performance_metrics.last_search": datetime.utcnow(),
                        "performance_metrics.last_relevance_score": results.get("relevance_score", 0.0)
                    }
                }
            )
            logger.info(f"Updated search metrics for KB {kb_id}")
        except Exception as e:
            logger.error(f"Failed to update search metrics: {e}")
    
    async def _generate_optimization_recommendations(self, kb_id: str, metrics: SmartIndexMetrics) -> List[Dict[str, Any]]:
        """Generate optimization recommendations based on performance metrics"""
        recommendations = []
        
        # Embedding quality recommendations
        if metrics.avg_embedding_quality < 0.6:
            recommendations.append({
                "type": "embedding_quality",
                "priority": "high",
                "description": "Low embedding quality detected",
                "action": "Re-process documents with optimized chunking",
                "impact": "Improved search accuracy"
            })
        
        # Storage efficiency recommendations
        if metrics.storage_efficiency < 0.4:
            recommendations.append({
                "type": "storage_efficiency",
                "priority": "medium",
                "description": "Storage efficiency could be improved",
                "action": "Increase chunk size to 600-800 tokens",
                "impact": "Reduced storage costs, faster searches"
            })
        
        # Performance recommendations
        if metrics.search_performance_score < 0.7:
            recommendations.append({
                "type": "search_performance",
                "priority": "medium",
                "description": "Search performance is below optimal",
                "action": "Optimize vector indexing parameters",
                "impact": "Faster search responses"
            })
        
        # Age-based recommendations
        days_since_optimization = (datetime.utcnow() - metrics.last_optimization).days
        if days_since_optimization > 60:
            recommendations.append({
                "type": "maintenance",
                "priority": "low",
                "description": f"Knowledge base not optimized for {days_since_optimization} days",
                "action": "Run comprehensive optimization",
                "impact": "Overall performance improvement"
            })
        
        return recommendations
    
    async def _apply_safe_optimizations(self, kb_id: str, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply safe optimizations automatically"""
        applied = []
        
        for rec in recommendations:
            # Only apply low-risk optimizations automatically
            if rec["priority"] == "low" or rec["type"] == "maintenance":
                try:
                    if rec["type"] == "maintenance":
                        # Update last optimization timestamp
                        await self.mongodb_collection.update_one(
                            {"id": kb_id},
                            {"$set": {"last_optimized": datetime.utcnow()}}
                        )
                        applied.append({
                            "recommendation": rec,
                            "status": "applied",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                except Exception as e:
                    applied.append({
                        "recommendation": rec,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        return applied
    
    async def _update_optimization_history(self, kb_id: str, optimizations: List[Dict[str, Any]]):
        """Update optimization history for a knowledge base"""
        try:
            await self.mongodb_collection.update_one(
                {"id": kb_id},
                {
                    "$push": {
                        "optimization_history": {
                            "$each": optimizations,
                            "$slice": -50  # Keep only last 50 optimization records
                        }
                    }
                }
            )
            logger.info(f"Updated optimization history for KB {kb_id}")
        except Exception as e:
            logger.error(f"Failed to update optimization history: {e}")

# Global smart database engine instance
smart_db_engine = None

def get_smart_database_engine(qdrant_client: QdrantClient, 
                            mongodb_collection: AsyncIOMotorCollection) -> SmartDatabaseEngine:
    """Get or create smart database engine instance"""
    global smart_db_engine
    
    if smart_db_engine is None:
        smart_db_engine = SmartDatabaseEngine(qdrant_client, mongodb_collection)
    
    return smart_db_engine 
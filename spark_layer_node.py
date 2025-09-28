import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import random
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_spark_layer_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for spark_layer node type
    
    This node works with vector embeddings for similarity and search operations.
    """
    logger.info(f"Executing Spark Layer node {node_id}")
    
    # Extract parameters
    mode = node_data.get("params", {}).get("mode", "text_to_embedding")
    provider = node_data.get("params", {}).get("provider", "openai")
    model = node_data.get("params", {}).get("model", "text-embedding-ada-002")
    input_format = node_data.get("params", {}).get("inputFormat", "single")
    dimension = node_data.get("params", {}).get("dimension", 1536)
    variable_name = node_data.get("params", {}).get("variableName", f"embedding_{node_id[:4]}")
    
    # Get input data
    input_data = inputs.get("input", "")
    
    try:
        result = {}
        
        if mode == "text_to_embedding":
            # Convert text to embedding vector
            if input_format == "single":
                # Process single text input
                if not isinstance(input_data, str):
                    input_data = str(input_data)
                
                # Generate simulated embedding vector
                embedding = generate_simulated_embedding(input_data, dimension)
                
                result = {
                    "embedding": embedding,
                    "dimension": dimension,
                    "text": input_data[:100] + "..." if len(input_data) > 100 else input_data,
                    "model": model,
                    "provider": provider
                }
            
            elif input_format == "batch":
                # Process multiple text inputs
                if isinstance(input_data, str):
                    # Split by lines
                    texts = input_data.strip().split("\n")
                elif isinstance(input_data, list):
                    texts = [str(item) for item in input_data]
                else:
                    texts = [str(input_data)]
                
                # Generate simulated embeddings for each text
                embeddings = [generate_simulated_embedding(text, dimension) for text in texts]
                
                result = {
                    "embeddings": embeddings,
                    "dimension": dimension,
                    "count": len(embeddings),
                    "model": model,
                    "provider": provider
                }
        
        elif mode == "embedding_similarity":
            # Calculate similarity between embeddings
            if isinstance(input_data, dict) and "embeddings" in input_data:
                # Input is a dict with multiple embeddings
                embeddings = input_data.get("embeddings", [])
                if len(embeddings) < 2:
                    return NodeResult(
                        output={"error": "At least two embeddings are required for similarity calculation"},
                        type="object",
                        execution_time=datetime.now().timestamp() - start_time,
                        status="error",
                        error="At least two embeddings are required",
                        node_id=node_id,
                        node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
                    )
                
                # Calculate similarities for all pairs
                similarities = []
                for i in range(len(embeddings)):
                    for j in range(i+1, len(embeddings)):
                        # Simulate similarity calculation
                        similarity = random.uniform(0.5, 1.0)  # Random value between 0.5 and 1.0
                        similarities.append({
                            "index1": i,
                            "index2": j,
                            "similarity": similarity
                        })
                
                result = {
                    "similarities": similarities,
                    "count": len(similarities),
                    "dimension": len(embeddings[0]) if embeddings and len(embeddings) > 0 else 0
                }
            
            else:
                # Try to extract embeddings from workflow data
                embedding1 = input_data
                embedding2 = inputs.get("embedding2", None)
                
                if embedding2 is None:
                    return NodeResult(
                        output={"error": "Second embedding not provided"},
                        type="object",
                        execution_time=datetime.now().timestamp() - start_time,
                        status="error",
                        error="Second embedding not provided",
                        node_id=node_id,
                        node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
                    )
                
                # Simulate similarity calculation
                similarity = random.uniform(0.5, 1.0)  # Random value between 0.5 and 1.0
                
                result = {
                    "similarity": similarity,
                    "embedding1": str(embedding1)[:50] + "...",
                    "embedding2": str(embedding2)[:50] + "..."
                }
        
        elif mode == "semantic_search":
            # Perform semantic search using embeddings
            query = input_data
            if isinstance(query, dict) and "text" in query:
                query = query.get("text", "")
            
            # Generate simulated search results
            search_results = []
            for i in range(5):  # Simulate 5 results
                score = 1.0 - (i * 0.1)  # Decreasing similarity scores
                search_results.append({
                    "id": f"doc_{i+1}",
                    "score": score,
                    "text": f"This is sample document {i+1} that would match the query in a real implementation.",
                    "metadata": {
                        "source": f"source_{i+1}",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            result = {
                "query": query,
                "results": search_results,
                "count": len(search_results),
                "model": model
            }
        
        # Store result in workflow data for variable access
        workflow_data[variable_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
        )
    
    except Exception as e:
        logger.error(f"Error in Spark Layer node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "Spark Layer")
        )

def generate_simulated_embedding(text: str, dimension: int) -> List[float]:
    """Generate a simulated embedding vector of the specified dimension"""
    # Use hash of text to seed random number generator for consistent results
    seed = hash(text) % 10000
    random.seed(seed)
    
    # Generate random values for embedding
    embedding = [random.uniform(-1, 1) for _ in range(dimension)]
    
    # Normalize to unit length
    magnitude = sum(x*x for x in embedding) ** 0.5
    if magnitude > 0:
        embedding = [x/magnitude for x in embedding]
    
    return embedding 
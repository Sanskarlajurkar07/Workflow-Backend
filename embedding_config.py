from models.knowledge_base import EmbeddingModel
from typing import Dict, Any

# Embedding model configurations
EMBEDDING_MODEL_CONFIG: Dict[EmbeddingModel, Dict[str, Any]] = {
    EmbeddingModel.TEXT_EMBEDDING_3_SMALL: {
        "dimension": 1536,
        "provider": "openai",
        "model_name": "text-embedding-3-small",
        "max_tokens": 8191
    },
    EmbeddingModel.TEXT_EMBEDDING_3_LARGE: {
        "dimension": 3072,
        "provider": "openai", 
        "model_name": "text-embedding-3-large",
        "max_tokens": 8191
    },
    EmbeddingModel.TEXT_EMBEDDING_ADA_002: {
        "dimension": 1536,
        "provider": "openai",
        "model_name": "text-embedding-ada-002",
        "max_tokens": 8191
    },
    EmbeddingModel.COHERE_EMBED_ENGLISH_V3: {
        "dimension": 1024,
        "provider": "cohere",
        "model_name": "embed-english-v3.0",
        "max_tokens": 512
    },
    EmbeddingModel.COHERE_EMBED_MULTILINGUAL_V3: {
        "dimension": 1024,
        "provider": "cohere",
        "model_name": "embed-multilingual-v3.0",
        "max_tokens": 512
    },
    EmbeddingModel.EMBED_MULTILINGUAL_V3: {
        "dimension": 1024,
        "provider": "cohere",
        "model_name": "embed-multilingual-v3.0",
        "max_tokens": 512
    }
}

def get_embedding_model_config(model) -> Dict[str, Any]:
    """Get the complete configuration for an embedding model"""
    # Handle string model names by converting to enum
    if isinstance(model, str):
        model_mapping = {
            "text-embedding-3-small": EmbeddingModel.TEXT_EMBEDDING_3_SMALL,
            "text-embedding-3-large": EmbeddingModel.TEXT_EMBEDDING_3_LARGE,
            "text-embedding-ada-002": EmbeddingModel.TEXT_EMBEDDING_ADA_002,
            "embed-english-v3.0": EmbeddingModel.COHERE_EMBED_ENGLISH_V3,
            "embed-multilingual-v3.0": EmbeddingModel.COHERE_EMBED_MULTILINGUAL_V3
        }
        model_enum = model_mapping.get(model, EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
    else:
        model_enum = model
    
    return EMBEDDING_MODEL_CONFIG.get(model_enum, EMBEDDING_MODEL_CONFIG[EmbeddingModel.TEXT_EMBEDDING_3_SMALL])

def get_embedding_dimension(model: EmbeddingModel) -> int:
    """Get the vector dimension for an embedding model"""
    return EMBEDDING_MODEL_CONFIG[model]["dimension"]

def get_embedding_provider(model: EmbeddingModel) -> str:
    """Get the provider for an embedding model"""
    return EMBEDDING_MODEL_CONFIG[model]["provider"]

def get_model_name(model: EmbeddingModel) -> str:
    """Get the actual model name to use with the provider API"""
    return EMBEDDING_MODEL_CONFIG[model]["model_name"]

def get_max_tokens(model: EmbeddingModel) -> int:
    """Get the maximum token limit for an embedding model"""
    return EMBEDDING_MODEL_CONFIG[model]["max_tokens"] 
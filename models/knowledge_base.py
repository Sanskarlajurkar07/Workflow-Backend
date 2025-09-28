from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DataSourceType(str, Enum):
    FILE = "file"
    URL = "url"
    INTEGRATION = "integration"
    RECURSIVE_URL = "recursive_url"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmbeddingModel(str, Enum):
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    COHERE_EMBED_ENGLISH_V3 = "embed-english-v3.0"
    COHERE_EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"
    EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"  # Keep for backward compatibility


class Document(BaseModel):
    id: str
    name: str
    source_type: DataSourceType
    source_path: str
    status: DocumentStatus = DocumentStatus.PENDING
    chunks: int = 0
    tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = {}


class KnowledgeBase(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    chunk_size: int = 400
    chunk_overlap: int = 0
    embedding_model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_3_SMALL
    advanced_doc_analysis: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    documents: List[Document] = []
    status: str = "active"
    
    @property
    def document_count(self) -> int:
        return len(self.documents)
    
    @property
    def total_tokens(self) -> int:
        return sum(doc.tokens for doc in self.documents)


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    chunk_size: int = 400
    chunk_overlap: int = 0
    embedding_model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_3_SMALL
    advanced_doc_analysis: bool = True


class DocumentCreate(BaseModel):
    name: str
    source_type: DataSourceType
    source_path: str
    metadata: Dict[str, Any] = {}


class KnowledgeBaseSync(BaseModel):
    id: str
    last_sync: datetime = Field(default_factory=datetime.now)
    status: str = "success"
    details: Optional[str] = None


class KnowledgeBaseSearch(BaseModel):
    kb_id: str
    query: str
    embedding_model: Optional[EmbeddingModel] = None
    top_k: int = 5


class SearchResult(BaseModel):
    document_id: str
    document_name: str
    chunk_text: str
    score: float
    metadata: Dict[str, Any] = {}


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total_results: int
    processing_time: float
    embedding_model: str 
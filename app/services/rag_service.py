"""
RAG Service using LlamaIndex for documentation retrieval.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple
from app.config import settings
from app.utils.logger import logger
from app.models import SourceDocument


class RAGService:
    """Service for Retrieval-Augmented Generation using LlamaIndex."""
    
    def __init__(self):
        """Initialize RAG service."""
        self._index = None
        self._retriever = None
        self._is_initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the RAG service by loading or creating the index.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            from llama_index.core import (
                VectorStoreIndex,
                StorageContext,
                load_index_from_storage,
                Settings as LlamaSettings
            )
            from llama_index.core.node_parser import SentenceSplitter
            
            # Configure LlamaIndex settings
            self._configure_llama_settings()
            
            storage_path = Path(settings.INDEX_STORAGE_PATH)
            
            # Try to load existing index
            if storage_path.exists() and any(storage_path.iterdir()):
                logger.info("Loading existing index from storage...")
                storage_context = StorageContext.from_defaults(
                    persist_dir=str(storage_path)
                )
                self._index = load_index_from_storage(storage_context)
                logger.info("Index loaded successfully")
            else:
                logger.info("No existing index found. Please run ingestion first.")
                return False
            
            # Create retriever (not query engine) to avoid LLM requirement
            # Use the index's retriever method with explicit settings
            self._retriever = self._index.as_retriever(
                similarity_top_k=settings.TOP_K_RESULTS
            )
            
            # Mark as initialized AFTER successful retriever creation
            self._is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            return False
    
    def _configure_llama_settings(self):
        """Configure LlamaIndex global settings."""
        from llama_index.core import Settings as LlamaSettings
        from llama_index.core.node_parser import SentenceSplitter
        
        # Configure text splitter
        LlamaSettings.text_splitter = SentenceSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        
        # Configure embedding model based on provider
        if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            from llama_index.embeddings.openai import OpenAIEmbedding
            LlamaSettings.embed_model = OpenAIEmbedding(
                model=settings.EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY
            )
            logger.info("Using OpenAI embeddings")
        elif settings.LLM_PROVIDER == "gemini" and settings.GOOGLE_API_KEY:
            from llama_index.embeddings.gemini import GeminiEmbedding
            LlamaSettings.embed_model = GeminiEmbedding(
                api_key=settings.GOOGLE_API_KEY
            )
            logger.info("Using Gemini embeddings")
        else:
            # Use local HuggingFace embeddings as fallback (no API key needed)
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            LlamaSettings.embed_model = HuggingFaceEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Using local HuggingFace embeddings (no API key required)")
        
        # Configure LLM for LlamaIndex internals (if available)
        if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            from llama_index.llms.openai import OpenAI
            LlamaSettings.llm = OpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY
            )
            logger.info("Using OpenAI LLM for LlamaIndex")
        else:
            # Keep disabled for non-OpenAI/fallback modes
            LlamaSettings.llm = None
            logger.info("LlamaIndex LLM disabled")

        logger.info("LlamaIndex settings configured")
    
    async def retrieve(self, query: str) -> Tuple[str, List[SourceDocument]]:
        """
        Retrieve relevant documentation for a query.
        
        Args:
            query: User's question
            
        Returns:
            Tuple of (combined context string, list of source documents)
        """
        if not self._is_initialized:
            if not self.initialize():
                return "", []
        
        try:
            # Use retriever to get relevant nodes (no LLM needed)
            nodes = self._retriever.retrieve(query)
            
            # Extract source nodes
            source_documents = []
            context_parts = []
            
            for node in nodes:
                content = node.node.get_content()
                source = node.node.metadata.get("file_name", "Unknown")
                score = node.score if hasattr(node, 'score') else None
                
                source_documents.append(SourceDocument(
                    content=content[:500] + "..." if len(content) > 500 else content,
                    source=source,
                    score=score
                ))
                context_parts.append(content)
            
            combined_context = "\n\n---\n\n".join(context_parts)
            
            logger.info(f"Retrieved {len(source_documents)} relevant documents")
            return combined_context, source_documents
            
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return "", []
    
    @property
    def is_ready(self) -> bool:
        """Check if the RAG service is ready to handle queries."""
        return self._is_initialized and self._index is not None
    
    def get_index_stats(self) -> dict:
        """Get statistics about the loaded index."""
        if not self._is_initialized:
            return {"status": "not_initialized"}
        
        try:
            doc_count = len(self._index.docstore.docs)
            return {
                "status": "ready",
                "document_count": doc_count,
                "top_k": settings.TOP_K_RESULTS
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

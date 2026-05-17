"""
RAG Service using LlamaIndex for documentation retrieval.
Supports local disk index or Pinecone vector store.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from app.config import settings
from app.models import SourceDocument
from app.services.vector_store import (
    build_index_from_documents,
    get_index_stats,
    load_documents,
    load_index,
    persist_local_index,
    pinecone_has_vectors,
    use_pinecone,
)
from app.utils.logger import logger


class RAGService:
    """Service for Retrieval-Augmented Generation using LlamaIndex."""

    def __init__(self):
        self._index = None
        self._retriever = None
        self._backend: Optional[str] = None
        self._is_initialized = False

    def initialize(self) -> bool:
        """
        Initialize the RAG service by loading or creating the index.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            index, backend = load_index()
            if index is not None:
                self._index = index
                self._backend = backend
            elif settings.AUTO_INGEST_ON_STARTUP:
                if not self._create_index_from_docs():
                    return False
            else:
                logger.info("No index available and auto-ingest disabled.")
                return False

            self._retriever = self._index.as_retriever(
                similarity_top_k=settings.TOP_K_RESULTS
            )
            self._is_initialized = True
            logger.info(
                f"RAG service ready (backend={self._backend or 'unknown'})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            return False

    def _create_index_from_docs(self) -> bool:
        """Create index from DOCS_DIRECTORY (local persist or Pinecone upsert)."""
        try:
            if use_pinecone() and pinecone_has_vectors():
                logger.info("Pinecone index already has vectors; skipping auto-ingest")
                index, backend = load_index()
                if index is None:
                    return False
                self._index = index
                self._backend = backend
                return True

            storage_path = Path(settings.INDEX_STORAGE_PATH)
            if not use_pinecone() and storage_path.exists() and any(storage_path.iterdir()):
                logger.info("Local index exists; skipping auto-ingest")
                index, backend = load_index()
                if index is None:
                    return False
                self._index = index
                self._backend = backend
                return True

            documents = load_documents()
            if not documents:
                logger.error("No documents found for auto-ingestion.")
                return False

            logger.info(f"Auto-ingesting {len(documents)} documents...")
            index, backend = build_index_from_documents(documents)
            self._index = index
            self._backend = backend

            if backend == "local":
                persist_local_index(index)

            return True
        except FileNotFoundError as e:
            logger.error(str(e))
            return False
        except Exception as e:
            logger.error(f"Auto-ingestion failed: {e}")
            return False

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
            nodes = self._retriever.retrieve(query)

            source_documents = []
            context_parts = []

            for node in nodes:
                content = node.node.get_content()
                source = node.node.metadata.get("file_name", "Unknown")
                score = node.score if hasattr(node, "score") else None

                source_documents.append(
                    SourceDocument(
                        content=content[:500] + "..."
                        if len(content) > 500
                        else content,
                        source=source,
                        score=score,
                    )
                )
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
            return get_index_stats(None)
        return get_index_stats(self._index)

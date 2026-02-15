"""
Documentation ingestion script for building the LlamaIndex vector store.

This script:
1. Loads documents from the docs directory
2. Processes and chunks the documents
3. Creates embeddings
4. Stores the index for later retrieval

Supported formats: PDF, Markdown, HTML, TXT, RST
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.utils.logger import logger


def load_documents(docs_path: str):
    """
    Load documents from the specified directory.
    """
    from llama_index.core import SimpleDirectoryReader

    docs_dir = Path(docs_path)

    if not docs_dir.exists():
        logger.error(f"Documentation directory not found: {docs_path}")
        raise FileNotFoundError(f"Directory not found: {docs_path}")

    supported_extensions = [".pdf", ".md", ".txt", ".html", ".rst", ".json"]

    logger.info(f"Loading documents from: {docs_path}")

    reader = SimpleDirectoryReader(
        input_dir=str(docs_dir),
        recursive=True,
        required_exts=supported_extensions,
        filename_as_id=True,
    )

    documents = reader.load_data()
    logger.info(f"Loaded {len(documents)} documents")

    return documents


def configure_settings():
    """Configure LlamaIndex settings for ingestion."""
    from llama_index.core import Settings as LlamaSettings
    from llama_index.core.node_parser import SentenceSplitter

    # Text chunking
    LlamaSettings.text_splitter = SentenceSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    # Embedding model selection
    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        from llama_index.embeddings.openai import OpenAIEmbedding

        LlamaSettings.embed_model = OpenAIEmbedding(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        logger.info("Using OpenAI embeddings")

    elif settings.LLM_PROVIDER == "gemini" and settings.GOOGLE_API_KEY:
        from llama_index.embeddings.gemini import GeminiEmbedding

        # ✅ Updated Gemini embedding model (fix for 404 error)
        LlamaSettings.embed_model = GeminiEmbedding(
            model_name="models/text-embedding-004",
            api_key=settings.GOOGLE_API_KEY,
        )

        logger.info("Using Gemini embeddings (updated model)")

    else:
        # Fallback local embedding (no API needed)
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        LlamaSettings.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        logger.info("Using HuggingFace embeddings (local)")


def create_index(documents):
    """Create vector store index."""
    from llama_index.core import VectorStoreIndex

    logger.info("Creating vector store index...")

    index = VectorStoreIndex.from_documents(
        documents,
        show_progress=True,
    )

    logger.info("Index created successfully")
    return index


def save_index(index, storage_path: str):
    """Save index to disk."""
    storage_dir = Path(storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Saving index to: {storage_path}")
    index.storage_context.persist(persist_dir=str(storage_dir))
    logger.info("Index saved successfully")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest documentation into vector store"
    )
    parser.add_argument(
        "--docs-path",
        type=str,
        default=settings.DOCS_DIRECTORY,
        help="Path to documentation directory",
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=settings.INDEX_STORAGE_PATH,
        help="Path to save the index",
    )

    args = parser.parse_args()

    try:
        configure_settings()

        documents = load_documents(args.docs_path)

        if not documents:
            logger.error("No documents found to index")
            sys.exit(1)

        index = create_index(documents)
        save_index(index, args.storage_path)

        logger.info("Ingestion completed successfully!")
        logger.info(f"Indexed {len(documents)} documents")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

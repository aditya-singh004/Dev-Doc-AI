"""
Vector store backends: local disk (LlamaIndex persist) or Pinecone.
Shared by RAGService and scripts/ingest_docs.py.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from app.config import settings
from app.utils.logger import logger

# Known embedding dimensions (must match Pinecone index dimension)
_EMBEDDING_DIMS = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "models/text-embedding-004": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


def use_pinecone() -> bool:
    """True when Pinecone should back the vector index."""
    mode = (settings.VECTOR_STORE or "local").strip().lower()
    has_creds = bool(settings.PINECONE_API_KEY and settings.PINECONE_INDEX_NAME)
    if mode == "pinecone":
        if not has_creds:
            logger.warning(
                "VECTOR_STORE=pinecone but PINECONE_API_KEY or PINECONE_INDEX_NAME missing"
            )
        return has_creds
    if mode == "auto":
        return has_creds
    return False


def get_embedding_dimension() -> int:
    if settings.PINECONE_DIMENSION and settings.PINECONE_DIMENSION > 0:
        return settings.PINECONE_DIMENSION
    model = settings.EMBEDDING_MODEL
    if model in _EMBEDDING_DIMS:
        return _EMBEDDING_DIMS[model]
    if settings.LLM_PROVIDER == "gemini":
        return 768
    if settings.LLM_PROVIDER == "openai":
        return 1536
    return 384


def configure_llama_settings() -> None:
    """Configure LlamaIndex global settings (chunking + embeddings)."""
    from llama_index.core import Settings as LlamaSettings
    from llama_index.core.node_parser import SentenceSplitter

    LlamaSettings.text_splitter = SentenceSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        from llama_index.embeddings.openai import OpenAIEmbedding

        LlamaSettings.embed_model = OpenAIEmbedding(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
        logger.info("Using OpenAI embeddings")
    elif settings.LLM_PROVIDER == "gemini" and settings.GOOGLE_API_KEY:
        from llama_index.embeddings.gemini import GeminiEmbedding

        LlamaSettings.embed_model = GeminiEmbedding(
            model_name="models/text-embedding-004",
            api_key=settings.GOOGLE_API_KEY,
        )
        logger.info("Using Gemini embeddings")
    else:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        LlamaSettings.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        logger.info("Using local HuggingFace embeddings")

    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        from llama_index.llms.openai import OpenAI

        LlamaSettings.llm = OpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
    else:
        LlamaSettings.llm = None


def _pinecone_client():
    from pinecone import Pinecone

    return Pinecone(api_key=settings.PINECONE_API_KEY)


def ensure_pinecone_index():
    """Create Pinecone index if missing; return the Index handle."""
    from pinecone import ServerlessSpec

    pc = _pinecone_client()
    name = settings.PINECONE_INDEX_NAME
    if not pc.has_index(name):
        if not settings.PINECONE_CREATE_INDEX:
            raise RuntimeError(
                f"Pinecone index '{name}' does not exist and PINECONE_CREATE_INDEX=false"
            )
        dim = get_embedding_dimension()
        logger.info(
            f"Creating Pinecone index '{name}' (dimension={dim}, "
            f"metric={settings.PINECONE_METRIC})"
        )
        pc.create_index(
            name=name,
            dimension=dim,
            metric=settings.PINECONE_METRIC,
            spec=ServerlessSpec(
                cloud=settings.PINECONE_CLOUD,
                region=settings.PINECONE_REGION,
            ),
        )
    return pc.Index(name)


def create_pinecone_vector_store():
    from llama_index.vector_stores.pinecone import PineconeVectorStore

    pinecone_index = ensure_pinecone_index()
    kwargs = {"pinecone_index": pinecone_index}
    namespace = (settings.PINECONE_NAMESPACE or "").strip()
    if namespace:
        kwargs["namespace"] = namespace
    return PineconeVectorStore(**kwargs)


def pinecone_has_vectors() -> bool:
    """True if the configured Pinecone index/namespace already has vectors."""
    try:
        idx = ensure_pinecone_index()
        stats = idx.describe_index_stats()
        namespace = (settings.PINECONE_NAMESPACE or "").strip()
        if namespace:
            ns_stats = stats.get("namespaces", {}).get(namespace, {})
            return int(ns_stats.get("vector_count", 0)) > 0
        return int(stats.get("total_vector_count", 0)) > 0
    except Exception as e:
        logger.warning(f"Could not read Pinecone index stats: {e}")
        return False


def load_documents(docs_path: Optional[str] = None):
    from llama_index.core import SimpleDirectoryReader

    path = Path(docs_path or settings.DOCS_DIRECTORY)
    if not path.exists():
        raise FileNotFoundError(f"Documentation directory not found: {path}")

    supported_extensions = [".pdf", ".md", ".txt", ".html", ".rst", ".json"]
    reader = SimpleDirectoryReader(
        input_dir=str(path),
        recursive=True,
        required_exts=supported_extensions,
        filename_as_id=True,
    )
    documents = reader.load_data()
    logger.info(f"Loaded {len(documents)} documents from {path}")
    return documents


def build_index_from_documents(documents) -> Tuple[object, str]:
    """
    Build a VectorStoreIndex from documents.

    Returns:
        (index, backend) where backend is 'pinecone' or 'local'
    """
    from llama_index.core import StorageContext, VectorStoreIndex

    configure_llama_settings()

    if use_pinecone():
        vector_store = create_pinecone_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,
        )
        logger.info("Index built and upserted to Pinecone")
        return index, "pinecone"

    index = VectorStoreIndex.from_documents(documents, show_progress=True)
    return index, "local"


def persist_local_index(index, storage_path: Optional[str] = None) -> None:
    path = Path(storage_path or settings.INDEX_STORAGE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(path))
    logger.info(f"Index persisted to {path}")


def load_index():
    """
    Load an existing index for retrieval.

    Returns:
        (index, backend) or (None, None) if unavailable
    """
    from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage

    configure_llama_settings()

    if use_pinecone():
        if not pinecone_has_vectors():
            return None, None
        vector_store = create_pinecone_vector_store()
        index = VectorStoreIndex.from_vector_store(vector_store)
        logger.info("Connected to Pinecone vector index")
        return index, "pinecone"

    storage_path = Path(settings.INDEX_STORAGE_PATH)
    if storage_path.exists() and any(storage_path.iterdir()):
        storage_context = StorageContext.from_defaults(persist_dir=str(storage_path))
        index = load_index_from_storage(storage_context)
        logger.info("Loaded local index from storage")
        return index, "local"

    return None, None


def get_index_stats(index=None) -> dict:
    """Stats for /api/v1/stats and health metadata."""
    backend = "pinecone" if use_pinecone() else "local"

    if use_pinecone():
        try:
            idx = ensure_pinecone_index()
            stats = idx.describe_index_stats()
            namespace = (settings.PINECONE_NAMESPACE or "").strip()
            if namespace:
                ns = stats.get("namespaces", {}).get(namespace, {})
                vector_count = int(ns.get("vector_count", 0))
            else:
                vector_count = int(stats.get("total_vector_count", 0))
            return {
                "status": "ready" if vector_count > 0 else "empty",
                "vector_store": backend,
                "index_name": settings.PINECONE_INDEX_NAME,
                "namespace": namespace or "(default)",
                "vector_count": vector_count,
                "top_k": settings.TOP_K_RESULTS,
            }
        except Exception as e:
            return {"status": "error", "vector_store": backend, "error": str(e)}

    if index is None:
        return {"status": "not_initialized", "vector_store": backend}

    try:
        doc_count = len(index.docstore.docs)
        return {
            "status": "ready",
            "vector_store": backend,
            "document_count": doc_count,
            "top_k": settings.TOP_K_RESULTS,
            "storage_path": settings.INDEX_STORAGE_PATH,
        }
    except Exception as e:
        return {"status": "error", "vector_store": backend, "error": str(e)}

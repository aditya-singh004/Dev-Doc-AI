"""
Documentation ingestion script for building the LlamaIndex vector store.

Supports local disk persistence or Pinecone (when VECTOR_STORE=pinecone).

Supported formats: PDF, Markdown, HTML, TXT, RST
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.vector_store import (
    build_index_from_documents,
    load_documents,
    persist_local_index,
    use_pinecone,
)
from app.utils.logger import logger


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest documentation into vector store (local or Pinecone)"
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
        help="Path to save local index (ignored for Pinecone)",
    )

    args = parser.parse_args()

    try:
        documents = load_documents(args.docs_path)
        if not documents:
            logger.error("No documents found to index")
            sys.exit(1)

        index, backend = build_index_from_documents(documents)

        if backend == "local":
            persist_local_index(index, args.storage_path)
        else:
            logger.info(
                f"Vectors upserted to Pinecone index '{settings.PINECONE_INDEX_NAME}'"
            )

        logger.info("Ingestion completed successfully!")
        logger.info(f"Backend: {backend} · indexed {len(documents)} source files")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

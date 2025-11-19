"""
RAG Knowledge Base System

Loads PDF documents (PhD thesis, OR papers) and makes them searchable
for improving LLM's domain understanding.

Usage:
    kb = KnowledgeBase("ML_approaches/RAG/papers", "ML_approaches/RAG/vectorstore")
    kb.load_papers()
    kb.build_index()
    context = kb.get_context("transportation problem", max_tokens=500)
"""

import os
from typing import List, Optional
from pathlib import Path
import logging

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    RAG knowledge base for OR domain documents.

    Loads PDFs, chunks them, creates embeddings, and stores in vector database
    for semantic search during LLM queries.
    """

    def __init__(
        self,
        papers_dir: str = "ML_approaches/RAG/papers",
        vectorstore_dir: str = "ML_approaches/RAG/vectorstore",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize knowledge base.

        Args:
            papers_dir: Directory containing PDF files
            vectorstore_dir: Directory to store Chroma vector database
            embedding_model: HuggingFace embedding model to use
        """
        self.papers_dir = Path(papers_dir)
        self.vectorstore_dir = Path(vectorstore_dir)
        self.embedding_model_name = embedding_model

        # Create directories if they don't exist
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        self.vectorstore = None
        self.documents = []

    def load_papers(self) -> int:
        """
        Load all PDF files from papers directory.

        Returns:
            Number of documents loaded
        """
        pdf_files = list(self.papers_dir.glob("*.pdf"))

        if not pdf_files:
            logger.warning(f"No PDF files found in {self.papers_dir}")
            logger.info("Add PDF files to ML_approaches/RAG/papers/ directory")
            return 0

        logger.info(f"Found {len(pdf_files)} PDF files")
        all_documents = []

        for pdf_path in pdf_files:
            try:
                logger.info(f"Loading: {pdf_path.name}")
                loader = PyPDFLoader(str(pdf_path))
                docs = loader.load()

                # Add metadata
                for doc in docs:
                    doc.metadata['source_file'] = pdf_path.name

                all_documents.extend(docs)
                logger.info(f"  Loaded {len(docs)} pages from {pdf_path.name}")

            except Exception as e:
                logger.error(f"Error loading {pdf_path.name}: {e}")
                continue

        self.documents = all_documents
        logger.info(f"Total pages loaded: {len(self.documents)}")
        return len(self.documents)

    def build_index(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> bool:
        """
        Chunk documents and build vector index.

        Args:
            chunk_size: Size of text chunks (characters)
            chunk_overlap: Overlap between chunks (characters)

        Returns:
            True if successful
        """
        if not self.documents:
            logger.error("No documents loaded. Call load_papers() first.")
            return False

        logger.info(f"Splitting documents into chunks (size={chunk_size}, overlap={chunk_overlap})")

        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        chunks = text_splitter.split_documents(self.documents)
        logger.info(f"Created {len(chunks)} chunks from {len(self.documents)} pages")

        # Create vector store
        logger.info("Building vector index (this may take a few minutes)...")
        try:
            self.vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=str(self.vectorstore_dir)
            )
            logger.info(f"Vector index saved to {self.vectorstore_dir}")
            return True

        except Exception as e:
            logger.error(f"Error building index: {e}")
            return False

    def load_index(self) -> bool:
        """
        Load existing vector index from disk.

        Returns:
            True if successful
        """
        try:
            self.vectorstore = Chroma(
                persist_directory=str(self.vectorstore_dir),
                embedding_function=self.embeddings
            )
            logger.info(f"Loaded existing index from {self.vectorstore_dir}")
            return True
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            return False

    def index_exists(self) -> bool:
        """Check if vector index exists on disk."""
        chroma_db = self.vectorstore_dir / "chroma.sqlite3"
        return chroma_db.exists()

    def search(self, query: str, k: int = 3) -> List[dict]:
        """
        Search for relevant document chunks.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of dicts with 'content' and 'metadata'
        """
        if self.vectorstore is None:
            if self.index_exists():
                self.load_index()
            else:
                logger.error("No index found. Build index first with build_index()")
                return []

        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return [
                {
                    'content': doc.page_content,
                    'metadata': doc.metadata
                }
                for doc in results
            ]
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def get_context(self, query: str, max_tokens: int = 800) -> str:
        """
        Get relevant context for a query, formatted for LLM prompt.

        Args:
            query: Query to search for
            max_tokens: Approximate max tokens (characters / 4)

        Returns:
            Formatted context string
        """
        max_chars = max_tokens * 4  # Rough estimate
        results = self.search(query, k=5)  # Get more results, truncate to fit

        if not results:
            return ""

        context_parts = []
        current_length = 0

        for i, result in enumerate(results):
            content = result['content'].strip()
            source = result['metadata'].get('source_file', 'Unknown')
            page = result['metadata'].get('page', '?')

            chunk = f"[Source: {source}, p.{page}]\n{content}\n"
            chunk_len = len(chunk)

            if current_length + chunk_len > max_chars:
                break

            context_parts.append(chunk)
            current_length += chunk_len

        return "\n---\n".join(context_parts)

    def stats(self) -> dict:
        """Get statistics about the knowledge base."""
        return {
            'papers_directory': str(self.papers_dir),
            'vectorstore_directory': str(self.vectorstore_dir),
            'index_exists': self.index_exists(),
            'documents_loaded': len(self.documents),
            'embedding_model': self.embedding_model_name
        }

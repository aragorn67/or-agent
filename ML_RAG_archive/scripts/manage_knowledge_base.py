#!/usr/bin/env python3
"""
Knowledge Base Management Script

Usage:
    python scripts/manage_knowledge_base.py build    # Build index from PDFs
    python scripts/manage_knowledge_base.py rebuild  # Rebuild index (deletes old)
    python scripts/manage_knowledge_base.py stats    # Show statistics
    python scripts/manage_knowledge_base.py search "query text"  # Test search
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.knowledge_base import KnowledgeBase

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def build_index(kb: KnowledgeBase):
    """Build knowledge base index."""
    print("=" * 60)
    print("Building Knowledge Base Index")
    print("=" * 60)

    # Load papers
    num_docs = kb.load_papers()
    if num_docs == 0:
        print("\n❌ No PDF files found in ML_approaches/RAG/papers/")
        print("\n📁 Please add PDF files to the ML_approaches/RAG/papers/ directory")
        print("   Then run this script again.")
        return False

    print(f"\n✓ Loaded {num_docs} pages from PDF files")

    # Build index
    print("\n🔨 Building vector index...")
    print("   This may take 5-10 minutes for large documents...")

    success = kb.build_index()

    if success:
        print("\n✅ Index built successfully!")
        print(f"   Saved to: ML_approaches/RAG/vectorstore/")
        return True
    else:
        print("\n❌ Failed to build index")
        return False


def rebuild_index(kb: KnowledgeBase):
    """Rebuild index from scratch."""
    import shutil

    print("=" * 60)
    print("Rebuilding Knowledge Base Index")
    print("=" * 60)

    # Delete old index
    if kb.vectorstore_dir.exists():
        print(f"\n🗑️  Deleting old index at {kb.vectorstore_dir}")
        shutil.rmtree(kb.vectorstore_dir)

    # Build new index
    return build_index(kb)


def show_stats(kb: KnowledgeBase):
    """Show knowledge base statistics."""
    stats = kb.stats()

    print("=" * 60)
    print("Knowledge Base Statistics")
    print("=" * 60)

    print(f"\n📁 Papers directory: {stats['papers_directory']}")
    print(f"📁 Vector store:     {stats['vectorstore_directory']}")
    print(f"🔧 Embedding model:  {stats['embedding_model']}")
    print(f"\n📊 Index exists:     {'✅ Yes' if stats['index_exists'] else '❌ No'}")
    print(f"📄 Documents loaded: {stats['documents_loaded']}")

    # Count PDF files
    pdf_count = len(list(Path(stats['papers_directory']).glob("*.pdf")))
    print(f"📚 PDF files found:  {pdf_count}")

    if pdf_count > 0:
        print("\nPDF files:")
        for pdf in Path(stats['papers_directory']).glob("*.pdf"):
            size_mb = pdf.stat().st_size / (1024 * 1024)
            print(f"  - {pdf.name} ({size_mb:.1f} MB)")

    if not stats['index_exists']:
        print("\n⚠️  No index found. Run 'build' to create one.")

    print()


def test_search(kb: KnowledgeBase, query: str):
    """Test search functionality."""
    print("=" * 60)
    print(f"Searching for: '{query}'")
    print("=" * 60)

    if not kb.index_exists():
        print("\n❌ No index found. Build index first with 'build' command.")
        return

    # Load index
    kb.load_index()

    # Search
    results = kb.search(query, k=3)

    if not results:
        print("\n❌ No results found.")
        return

    print(f"\n✅ Found {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        source = result['metadata'].get('source_file', 'Unknown')
        page = result['metadata'].get('page', '?')
        content = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']

        print(f"[{i}] {source}, page {page}")
        print(f"    {content}")
        print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    # Initialize knowledge base
    kb = KnowledgeBase()

    if command == "build":
        build_index(kb)

    elif command == "rebuild":
        rebuild_index(kb)

    elif command == "stats":
        show_stats(kb)

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python scripts/manage_knowledge_base.py search \"query text\"")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        test_search(kb, query)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

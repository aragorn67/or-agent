# 📚 RAG System Guide

**Retrieval-Augmented Generation** for improved OR problem understanding

---

## 🎯 What is RAG?

RAG enhances the LLM by giving it access to your PhD thesis and OR papers. When solving problems, the system:
1. Searches your documents for relevant context
2. Adds that context to the LLM prompt
3. Gets better, more informed responses

**Benefits:**
- Better problem classification (uses definitions from your papers)
- Better parameter extraction (follows notation you use)
- Better explanations (uses your terminology)
- Can cite sources: "According to [thesis, p.45]..."

---

## 🚀 Quick Start

### 1. Add Your PDFs

```bash
# Copy PDFs to the papers directory
cp ~/Downloads/thesis.pdf knowledge/papers/
cp ~/Documents/OR_papers/*.pdf knowledge/papers/
```

### 2. Build the Index

```bash
source Tolis_Env/bin/activate
python scripts/manage_knowledge_base.py build
```

This takes 5-10 minutes and only needs to be done once (or when you add new PDFs).

### 3. It Just Works!

The RAG system is now active. When you run tests or use the API, it automatically:
- Searches your papers for relevant context
- Includes that context in LLM prompts
- No code changes needed!

---

## 📁 Directory Structure

```
knowledge/
├── papers/              # ← PUT YOUR PDFs HERE
│   ├── thesis.pdf
│   ├── winston_OR.pdf
│   └── hillier_lieberman.pdf
│
├── vectorstore/         # ← AUTO-GENERATED (don't touch)
│   └── chroma.sqlite3
│
└── README.md            # Quick reference
```

---

## 🔧 Management Commands

### Check Status
```bash
python scripts/manage_knowledge_base.py stats
```

Shows:
- Number of PDF files found
- Index status (exists/missing)
- Embedding model being used

### Build Index (First Time)
```bash
python scripts/manage_knowledge_base.py build
```

Loads all PDFs, chunks them, creates embeddings, saves to vector database.

### Rebuild Index (After Adding PDFs)
```bash
python scripts/manage_knowledge_base.py rebuild
```

Deletes old index and builds fresh one from current PDFs.

### Test Search
```bash
python scripts/manage_knowledge_base.py search "transportation problem"
```

Tests retrieval - shows top 3 relevant chunks from your papers.

---

## 💡 What PDFs to Add?

**Highly Recommended:**
- Your PhD thesis
- Classic OR textbooks (Winston, Hillier & Lieberman)
- Papers on problem types you work with
- Conference proceedings (INFORMS, etc.)

**File Requirements:**
- ✅ PDF format only
- ✅ Text-based PDFs (not scanned images)
- ✅ English language works best
- ✅ Any size (system handles chunking)

**Good Candidates:**
- Transportation problem papers
- Scheduling algorithms research
- Linear programming theory
- Operations research handbooks

---

## 🔬 How It Works (Technical)

### Step 1: Loading
```python
# Reads all PDFs from knowledge/papers/
loader = PyPDFLoader("knowledge/papers/thesis.pdf")
documents = loader.load()
```

### Step 2: Chunking
```python
# Splits into 1000-char chunks with 200-char overlap
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = text_splitter.split_documents(documents)
```

### Step 3: Embedding
```python
# Converts text to vectors using sentence-transformers
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
```

### Step 4: Storage
```python
# Stores in Chroma vector database
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="knowledge/vectorstore"
)
```

### Step 5: Retrieval (During Use)
```python
# When LLM needs context, searches for relevant chunks
results = vectorstore.similarity_search(
    "transportation problem parameters",
    k=3  # Top 3 most relevant chunks
)
```

---

## 📊 Integration Points

RAG context is automatically added to:

### 1. Transportation Specialist
```python
# Searches for: "transportation problem parameters supply demand cost"
# Adds top 500 tokens of context to extraction prompt
```

### 2. Scheduling Specialist
```python
# Searches for: "scheduling problem makespan processing time changeover"
# Adds top 500 tokens of context to extraction prompt
```

### 3. Future Specialists
When you add new specialists (assignment, knapsack, etc.), they'll automatically get RAG support by passing `knowledge_base` parameter.

---

## 💾 Storage Requirements

| Component | Size |
|-----------|------|
| Your PDFs | 10-100 MB each |
| Vector Database | ~2-3x PDF size |
| Embedding Model | ~90 MB (one-time download) |
| **Total** | **~400-600 MB** |

---

## ⚡ Performance

| Operation | Time |
|-----------|------|
| Initial index build | 5-10 minutes |
| Rebuild index | 5-10 minutes |
| First search | ~1-2 seconds |
| Subsequent searches | ~50-100ms |
| Per-request overhead | ~100ms |

---

## 🎛️ Configuration

### Change Chunk Size
Edit `scripts/manage_knowledge_base.py`:
```python
kb.build_index(
    chunk_size=1500,  # Larger chunks (default: 1000)
    chunk_overlap=300  # More overlap (default: 200)
)
```

### Change Embedding Model
Edit `llm/knowledge_base.py`:
```python
kb = KnowledgeBase(
    embedding_model="sentence-transformers/all-mpnet-base-v2"  # Better but slower
)
```

### Change Context Length
Edit `llm/*_specialist.py`:
```python
rag_context = self.kb.get_context(
    query,
    max_tokens=800  # More context (default: 500)
)
```

---

## 🧪 Testing RAG

### Test 1: Verify Import
```bash
source Tolis_Env/bin/activate
python -c "from llm.knowledge_base import KnowledgeBase; print('✅ OK')"
```

### Test 2: Build Index
```bash
python scripts/manage_knowledge_base.py build
```

### Test 3: Test Search
```bash
python scripts/manage_knowledge_base.py search "linear programming"
```

### Test 4: Run Integration Test
```bash
cd tests
python Overall_Test.py
```

RAG context will be automatically used in parameter extraction.

---

## 🐛 Troubleshooting

### "No PDF files found"
- Check PDFs are in `knowledge/papers/` directory
- File extension must be `.pdf` (lowercase)

### "Failed to build index"
- Check disk space (need ~500MB free)
- Check PDF files aren't corrupted
- Try with one PDF first to isolate issues

### "Chroma database error"
- Delete `knowledge/vectorstore/` folder
- Run `rebuild` command

### "Model download fails"
- Check internet connection
- Model downloads from HuggingFace (~90MB)
- Set `HF_HOME` environment variable if behind proxy

### "Out of memory"
- Reduce `chunk_size` to 500
- Process fewer PDFs at once
- Increase system RAM

---

## 🚫 What Not to Commit to Git

Already in `.gitignore`:
```
knowledge/papers/*.pdf       # Your PDFs (private)
knowledge/vectorstore/        # Generated index (large)
```

**DO commit:**
- `knowledge/README.md` (documentation)
- Empty `knowledge/papers/.gitkeep` (preserves directory)

---

## 🔮 Future Enhancements

- [ ] Support for more document types (DOCX, TXT, HTML)
- [ ] Multi-language support
- [ ] Hybrid search (keyword + semantic)
- [ ] Re-ranking retrieved chunks
- [ ] Citation extraction and linking
- [ ] Automatic paper categorization

---

## 📞 Need Help?

1. Check `knowledge/README.md` for quick reference
2. Run `python scripts/manage_knowledge_base.py stats` to check status
3. Look at logs in terminal output
4. Test search to verify retrieval works

---

**Last updated:** 2025-11-08
**Status:** ✅ Fully implemented and tested

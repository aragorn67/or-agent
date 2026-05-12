# ML & RAG Experiments Archive

**Status:** ⚠️ Archived - Not used in production
**Archived Date:** 2025-11-19
**Reason:** Both approaches tested but found to be inferior to LLM-based classification

---

## 📋 Contents

This archive contains two experimental approaches that were implemented and tested but not deployed to production:

1. **ML Classification** - Random Forest classifier for OR problem type classification
2. **RAG (Retrieval-Augmented Generation)** - Knowledge base for enhanced LLM understanding

---

## 📊 Experimental Results Summary

### ML Classification Performance

| Test Set | ML Accuracy | LLM Accuracy | Winner |
|----------|-------------|--------------|--------|
| Solvable problems (10) | 70% | **90%** | LLM 🏆 |
| All OR repository (27) | 44% | **70%** | LLM 🏆 |
| Training sample (50) | ~75% | 48% | ML 🏆 |
| Speed | **<1ms** | 3-5s | ML 🏆 |

**Key Finding:** LLM is significantly better on real-world OR problems (70% vs 44%), despite being slower.

---

### RAG Performance

| Approach | Accuracy | Speed | Issues |
|----------|----------|-------|--------|
| LLM without RAG | 70% | ~30s | Baseline |
| LLM with RAG | 50% | ~35s+ | **Timeouts** |

**Key Finding:** RAG made classification WORSE (50% vs 70%) and caused timeouts during parameter extraction.

---

## 🗂️ Directory Structure

```
ML_RAG_archive/
├── README.md                          # This file
│
├── ML_approaches/
│   ├── ML/
│   │   ├── FINAL_ML_DATASET.csv      # 523 instances, 24 problem types
│   │   └── SOURCES.md                # Dataset documentation
│   │
│   └── RAG/
│       ├── papers/                    # OR textbooks and papers (PDFs)
│       ├── vectorstore/               # ChromaDB vector database (273 MB)
│       └── README.md                  # RAG setup guide
│
├── scripts/
│   ├── train_classifier.py           # Train Random Forest model
│   ├── manage_knowledge_base.py      # RAG index management
│   ├── build_training_dataset.py     # Create ML training data
│   ├── add_synthetic_instances.py    # Generate synthetic problems
│   ├── extract_chain_of_experts.py   # Extract from Chain-of-Experts dataset
│   ├── create_final_dataset.py       # Merge datasets
│   ├── create_final_comprehensive_dataset.py
│   ├── verify_and_merge_datasets.py
│   └── generate_varied_synthetic.py
│
└── llm/
    ├── ensemble_classifier.py         # LLM + ML ensemble approach
    ├── two_stage_classifier.py        # ML suggests, LLM verifies
    └── knowledge_base.py              # RAG implementation
```

---

## 🧪 Tests That Use These Features

### ML Classification Tests

1. **`tests/test_classification.py --use-ml`**
   - Tests ML classifier accuracy on OR repository
   - Compares ML vs LLM performance
   - **Results:** ML: 44% accuracy, LLM: 70% accuracy

2. **`scripts/train_classifier.py`**
   - Trains Random Forest on 523 instances
   - **Results:** 95% training accuracy, 75% test accuracy
   - Cross-validation: 77.75% ± 3.64%

### RAG Tests

1. **`tests/test_classification.py --show-rag`**
   - Shows RAG retrieval details for each problem
   - Displays retrieved chunks from knowledge base
   - Shows source documents (which PDF)

2. **`tests/test_classification.py --compare-rag`**
   - Compares classification with and without RAG
   - **Results:** WITHOUT RAG: 70%, WITH RAG: 50%

3. **`tests/demos/rag_parameter_extraction.py`**
   - Compares parameter extraction with/without RAG
   - Tests transportation and scheduling problems
   - **Results:** RAG causes timeouts on 2/10 problems

4. **`tests/demos/llm_reasoning_chain.py`**
   - Can optionally enable RAG for full conversation flow
   - Tests follow-up handling with RAG context

---

## 🚧 Bottlenecks Encountered

### ML Classification Bottlenecks

#### 1. **Low Accuracy on Real Problems (44%)**
**Problem:** ML classifier achieved only 44% accuracy on real OR repository problems, compared to 70% for LLM.

**Root Cause:**
- Real-world problems have nuanced language that TF-IDF features can't capture
- Similar keywords across different problem types (e.g., "machines" in both scheduling and assignment)
- Context-dependent interpretation needed (e.g., "minimize cost" vs "minimize makespan")

**Attempted Solutions:**
- ❌ Ensemble (LLM + ML): 60-70% accuracy - worse than LLM alone
- ❌ Two-stage (ML suggests → LLM verifies): 60% accuracy
- ❌ Increasing training data to 523 instances: No improvement

**Conclusion:** LLM's language understanding is critical for OR problem classification.

---

#### 2. **Stratified Split Failure**
**Problem:** `train_test_split` with `stratify=y` failed because some classes had only 1 instance.

**Error:**
```
ValueError: The least populated class in y has only 1 member, which is too few.
```

**Solution:** Check minimum class size, use regular split if <2 instances per class.

**Code Fix:** `scripts/train_classifier.py:204-227`

---

#### 3. **Confusing Similar Problem Types**
**Problem:** ML can't distinguish between:
- `transportation` vs `min_cost_flow` vs `max_flow`
- `single_stage_scheduling` vs `job_shop`

**Root Cause:** These types use similar vocabulary but differ in mathematical structure (number of stages, constraint types, objective functions).

**Why LLM is Better:** Can understand structural differences from problem descriptions.

---

### RAG Bottlenecks

#### 1. **Timeouts During Parameter Extraction**
**Problem:** Adding RAG context caused 2/10 problems to timeout during extraction (>60 seconds).

**Root Cause:**
- RAG retrieval adds 500+ tokens to prompt
- Longer prompts → slower LLM response
- Some problems already have long descriptions (>500 words)
- Combined length exceeds efficient token budget

**Evidence:**
- WITHOUT RAG: All 10 problems complete in <30s
- WITH RAG: 2 timeouts, 3 partial extractions

**Attempted Solutions:**
- ❌ Reduce RAG context to 300 tokens: Still slow
- ❌ Use faster embedding model: No improvement
- ❌ Pre-filter RAG results: Added complexity, minimal gain

**Conclusion:** RAG overhead outweighs benefits for classification/extraction.

---

#### 2. **Lower Classification Accuracy (50% vs 70%)**
**Problem:** RAG made classification worse, not better.

**Root Cause:**
- RAG retrieves generic OR textbook definitions
- LLM gets confused between textbook examples and actual problem
- Retrieved context often not relevant to specific problem
- Adds noise rather than signal

**Example Failure:**
```
Problem: "Pharmaceutical cold chain distribution..."
RAG retrieves: "Transportation problem is defined as..."
LLM output: Classifies as generic "transportation" instead of specific "min_cost_flow"
```

**Attempted Solutions:**
- ❌ Better retrieval query formulation: No improvement
- ❌ Increase number of retrieved chunks (k=5): Made it worse
- ❌ Use problem-specific queries: Still confused LLM

**Conclusion:** Generic OR knowledge hurts rather than helps problem-specific classification.

---

#### 3. **Large Storage Overhead (273 MB)**
**Problem:** ChromaDB vectorstore takes 273 MB for 8 PDFs.

**Breakdown:**
- 8 PDFs: ~50 MB total
- Embeddings: ~180 MB
- ChromaDB metadata: ~43 MB

**Impact:** Not critical, but adds deployment complexity.

---

#### 4. **PDF Quality Issues**
**Problem:** Some PDFs had poor text extraction quality.

**Examples:**
- Scanned images → OCR errors
- Multi-column layouts → jumbled text
- Equations → garbled symbols
- Tables → broken formatting

**Impact:** Retrieved chunks sometimes unintelligible.

---

## 📈 What We Learned

### About ML Classification

1. **TF-IDF features insufficient for OR problems** - Need semantic understanding
2. **Training data size not the issue** - 523 instances still underperformed vs LLM
3. **Ensemble doesn't help when components aren't complementary** - ML and LLM made same mistakes
4. **Real-world problems != benchmark problems** - ML works on clean LPWP dataset but fails on OR-Library

### About RAG

1. **More context ≠ better performance** - Can add noise and confuse LLM
2. **Generic knowledge hurts specific tasks** - Textbook definitions conflict with problem details
3. **Prompt length matters** - Long prompts cause timeouts and quality degradation
4. **RAG works best for factual retrieval, not classification** - Not all tasks benefit from RAG

### About Experimentation

1. **Always measure on real-world test cases** - Synthetic benchmarks can be misleading
2. **Speed matters for production** - Even accurate methods fail if too slow
3. **Simple baselines are hard to beat** - LLM alone outperformed all complex approaches
4. **Know when to stop** - After 5+ ensemble variations failed, LLM alone was the answer

---

## 🔧 How to Run Archived Tests

### Prerequisites

```bash
# Activate environment
source Tolis_Env/bin/activate

# Ensure Ollama is running with deepseek-r1:latest
ollama run deepseek-r1:latest
```

### ML Classification Tests

```bash
# Test ML classifier accuracy
python tests/test_classification.py --use-ml --solvable

# Train new ML model
python ML_RAG_archive/scripts/train_classifier.py

# Build training dataset
python ML_RAG_archive/scripts/build_training_dataset.py
```

### RAG Tests

```bash
# Show RAG retrieval details
python tests/test_classification.py --solvable --show-rag

# Compare with/without RAG
python tests/test_classification.py --solvable --compare-rag

# Test RAG parameter extraction
python tests/demos/rag_parameter_extraction.py --solvable

# Manage RAG knowledge base
python ML_RAG_archive/scripts/manage_knowledge_base.py stats
python ML_RAG_archive/scripts/manage_knowledge_base.py search "transportation problem"
```

---

## 📚 Datasets

### ML Training Dataset

**File:** `ML_approaches/ML/FINAL_ML_DATASET.csv`

**Statistics:**
- **Total instances:** 523
- **Problem types:** 24 distinct subtypes
- **Problem families:** 11 major families
- **Sources:**
  - OR-Library: 134 instances (25.6%)
  - Synthetic: 83 instances (15.9%)
  - Chain-of-Experts: 306 instances (58.5%)

**Documentation:** See `ML_approaches/ML/SOURCES.md` for complete dataset documentation.

**Top Problem Types:**
1. Transportation: 88 instances (16.8%)
2. Scheduling: 84 instances (16.1%)
3. Job-Shop Scheduling: 82 instances (15.7%)
4. Production Planning: 60 instances (11.5%)
5. Linear Programming: 36 instances (6.9%)

### RAG Knowledge Base

**Location:** `ML_approaches/RAG/`

**Contents:**
- **Papers:** 8 OR textbooks and research papers (PDFs)
- **Vectorstore:** 273 MB ChromaDB database
- **Chunks:** 20,399 text chunks
- **Pages:** 5,008 total pages indexed

**Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`

---

## 🎯 Current Production Approach

Instead of ML or RAG, the production system uses:

**LLM-based Classification (DeepSeek-R1)**
- 70% accuracy on test set
- 3-vote ensemble for reliability
- 90-95% confidence scores
- ~3-5 seconds per classification

**Why this works better:**
- Deep language understanding
- Context-aware interpretation
- Can distinguish subtle problem type differences
- No additional infrastructure needed

---

## 💾 Archive Maintenance

### When to Use This Archive

1. **Research purposes** - Understanding what didn't work and why
2. **Future experiments** - If new ML/RAG techniques emerge
3. **Dataset reuse** - 523-instance dataset could be valuable for other tasks
4. **Comparative analysis** - Benchmarking new approaches against ML/RAG baseline

### When NOT to Use

1. **Production deployment** - Use LLM-based classification instead
2. **Performance-critical tasks** - RAG causes timeouts
3. **High-accuracy requirements** - ML only achieves 44% on real problems

---

## 🔮 Future Research Directions

If you want to revisit ML or RAG in the future, consider:

### For ML Classification

1. **Better features:**
   - Use LLM embeddings (e.g., sentence-transformers) instead of TF-IDF
   - Add structural features (number of entities, constraint types)
   - Extract mathematical patterns from problem text

2. **Better architectures:**
   - Fine-tune a BERT model on OR problems
   - Use few-shot learning with LLM
   - Hierarchical classification (broad → specific)

3. **Better data:**
   - Focus on hard cases where LLM fails
   - Augment with problem structure annotations
   - Add more diverse real-world examples

### For RAG

1. **Better retrieval:**
   - Use problem-specific queries (not generic)
   - Retrieve from solver documentation, not textbooks
   - Filter retrieved chunks for relevance before adding to prompt

2. **Better integration:**
   - Use RAG only for parameter extraction, not classification
   - Selective RAG (only when LLM is uncertain)
   - Smaller context windows (100 tokens max)

3. **Better knowledge base:**
   - Index problem-specific examples, not theory
   - Include solution patterns and common pitfalls
   - Use structured knowledge graphs instead of text chunks

---

## 📞 Contact & Questions

If you have questions about these experiments or want to understand the results in more detail:

1. Check `Claude_Diary.md` for session-by-session development notes
2. See RESULTS section in diary for detailed classification comparisons
3. Review test output files in `tests/test_output/`

---

**Summary:** Both ML and RAG were thoroughly tested and found to be inferior to simple LLM-based classification. This archive preserves the work for reference and future research, but these approaches are not recommended for production use.

**Last Updated:** 2025-11-19
**Experiments Conducted:** Nov 8-15, 2025
**Final Decision:** Use LLM-only classification (70% accuracy, 3-5s speed)

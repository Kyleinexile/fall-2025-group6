# AFSC → KSA Extraction Pipeline

**Production-ready extraction pipeline** that transforms Air Force Specialty Code (AFSC) job descriptions into structured Knowledge, Skills, and Abilities (KSAs) with taxonomy alignment.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![LAiSER](https://img.shields.io/badge/LAiSER-0.1+-green.svg)
![Neo4j](https://img.shields.io/badge/neo4j-5.0+-blue.svg)

---

## 🎯 Quick Stats

- ✅ **12 AFSCs processed** with 330+ KSAs extracted
- ✅ **~$0.005 per AFSC** processing cost (LAiSER-only mode)
- ✅ **3-8 seconds** average processing time
- ✅ **LAiSER + Gemini integration** for skill extraction and taxonomy alignment

---

## 🏗️ Architecture Overview

### Pipeline Stages

```
┌─────────────┐
│ AFSC Text   │
│ (PDF/Plain) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPROCESSING (preprocess.py)                            │
│    • Remove PDF artifacts (headers, footers, page numbers)  │
│    • Fix hyphenated line breaks                             │
│    • Normalize whitespace → clean narrative                 │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SKILL EXTRACTION (extract_laiser.py)                     │
│    • LAiSER + Gemini: Extract 20-30 skills per AFSC        │
│    • Built-in ESCO taxonomy alignment                       │
│    • Fallback: Regex heuristics if LAiSER unavailable      │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. QUALITY FILTERING (quality_filter.py)                    │
│    • Length constraints (3-80 characters)                   │
│    • Domain relevance filtering                             │
│    • Canonical text mapping                                 │
│    • Exact deduplication on (type, text)                    │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. LLM ENHANCEMENT (enhance_llm.py) - OPTIONAL              │
│    • Generate complementary Knowledge & Ability items       │
│    • Default: DISABLED (cost optimization)                  │
│    • When enabled: Gemini Flash, 1024 token max            │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. FUZZY DEDUPLICATION (dedupe.py)                          │
│    • Hybrid similarity: 60% Jaccard + 40% difflib          │
│    • Threshold: 0.86 (optimized for short KSA text)        │
│    • Winner selection: ESCO > Confidence > Source > Length │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. GRAPH PERSISTENCE (graph_writer_v2.py)                   │
│    • Neo4j idempotent MERGE operations                      │
│    • Nodes: (:AFSC), (:KSA), (:ESCOSkill)                  │
│    • Relationships: [:REQUIRES], [:ALIGNS_TO]               │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│  Neo4j      │
│  Graph DB   │
└─────────────┘
```

---

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- Neo4j Aura account (or local Neo4j instance)
- Google Gemini API key (for LAiSER)
- Optional: OpenAI/Anthropic API keys (for LLM enhancement)

### Setup

```bash
# Clone repository
git clone https://github.com/Kyleinexile/fall-2025-group6.git
cd fall-2025-group6

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys and Neo4j credentials
```

### Required Environment Variables

```bash
# Neo4j Configuration (Required)
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# LAiSER Configuration (Required)
GEMINI_API_KEY=your-gemini-api-key
USE_LAISER=true
LAISER_ALIGN_TOPK=25

# LLM Enhancement (Optional - Disabled by Default)
USE_LLM_ENHANCER=false
LLM_PROVIDER=gemini
LLM_MODEL_GEMINI=gemini-2.0-flash

# Quality Filtering
QUALITY_MIN_LEN=3
QUALITY_MAX_LEN=80
LOW_CONF_SKILL_THRESHOLD=0.60
STRICT_SKILL_FILTER=false

# Deduplication
AGGRESSIVE_DEDUPE=true
```

---

## 💻 Usage

### Python API

```python
from afsc_pipeline.pipeline import run_pipeline
from neo4j import GraphDatabase

# Connect to Neo4j
driver = GraphDatabase.driver(
    "neo4j+s://your-instance.databases.neo4j.io",
    auth=("neo4j", "your-password")
)

# Process a single AFSC
with driver.session() as session:
    summary = run_pipeline(
        afsc_code="1N0X1",
        afsc_raw_text=open("afsc_text.txt").read(),
        neo4j_session=session,
    )

print(f"Extracted {summary['n_items_after_dedupe']} KSAs")
```

### Demo Mode (No Database Writes)

```python
from afsc_pipeline.pipeline import run_pipeline_demo

summary = run_pipeline_demo(
    afsc_code="1N0X1",
    afsc_raw_text="Your AFSC text here...",
)

# Results available in summary['items']
for item in summary['items']:
    print(f"{item.item_type.value}: {item.text}")
```

### Streamlit Web Interface

```bash
streamlit run src/streamlit_app/Home.py
```

Navigate to:
- **Try It Yourself**: Interactive PDF search & extraction
- **Explore KSAs**: Query and filter existing KSAs
- **Admin Tools**: Batch processing (write to database)
- **Documentation**: Complete technical reference

---

## ⚙️ Configuration Guide

### 💰 Cost Optimization

**Default configuration prioritizes cost efficiency:**

**1. LLM Enhancement Disabled** (`USE_LLM_ENHANCER=false`)
- LAiSER extraction alone achieves coverage goals
- Enable only when Knowledge/Ability items are required

**2. Gemini Flash Model** (when LLM enabled)
- Cheapest available option (~$0.075 per 1M input tokens)
- Alternative: `gpt-4o-mini` (~$0.15 per 1M tokens)

**3. Token Limits**
- Input limit: 5000 characters (full AFSC context)
- Output limit: 1024 tokens
- Max new items: 6 per AFSC

**Cost breakdown per AFSC:**

| Configuration | Per AFSC | 12 AFSCs | 200 AFSCs |
|--------------|----------|----------|-----------|
| LAiSER-only | $0.005 | $0.06 | $1.00 |
| + Gemini Flash | $0.005-0.010 | $0.06-0.12 | $1.00-2.00 |
| + GPT-4o-mini | $0.015-0.025 | $0.18-0.30 | $3.00-5.00 |
| + Claude Sonnet | $0.050-0.100 | $0.60-1.20 | $10-20 |

### 🔍 LAiSER Configuration

LAiSER is the primary extraction engine with built-in ESCO alignment:

```python
# Settings in extract_laiser.py
model_id = "gemini"           # Gemini backend
use_gpu = False               # CPU-only (cloud compatible)
LAISER_ALIGN_TOPK = 25        # Return top 25 skills
method = "ksa"                # KSA extraction mode
input_type = "job_desc"       # Job description format
```

**Key Features:**
- ✅ Extracts action-oriented skill phrases
- ✅ Assigns confidence scores (0-1 range)
- ✅ Provides ESCO taxonomy IDs automatically
- ✅ Graceful fallback to regex heuristics if API fails

**Why Gemini?**
- Cost-effective for skill extraction workloads
- Built-in ESCO catalog access
- Fast inference (2-5 seconds per AFSC)

### 🔄 Deduplication Strategy

**NOT using FAISS** - Custom hybrid approach optimized for short text:

```python
# Similarity calculation
similarity = 0.6 * jaccard_similarity + 0.4 * difflib_ratio

# Default threshold
similarity_threshold = 0.86  # Tuned for 10-60 character KSA phrases
```

**Winner selection criteria (priority order):**
1. Has ESCO ID (highest priority)
2. Higher confidence score
3. Source is "laiser"
4. Longer text length (tiebreaker)

**Why not FAISS?**

| Aspect | FAISS | Custom Hybrid |
|--------|-------|---------------|
| Dataset Size | Millions of vectors | 20-50 items |
| Performance | Approximate (ANN) | Exact similarity |
| Explainability | Black box | Clear formula (60% + 40%) |
| Complexity | High (external dependency) | Low (pure Python) |
| Our Use Case | ❌ Overkill | ✅ Just right |

**Performance:**
- Deduplication reduction: 10-20% of items removed
- Execution time: <100ms per AFSC
- False positive rate: <1% (verified manually)

### 🎚️ Quality Filtering

Configurable via environment variables:

```bash
# Strict mode: Require ESCO IDs for low-confidence skills
STRICT_SKILL_FILTER=false

# Confidence threshold for strict filtering
LOW_CONF_SKILL_THRESHOLD=0.60
```

**Filter stages:**
1. Length validation (3-80 chars)
2. Banned phrase removal
3. Canonical text mapping
4. Exact deduplication

---

## 📊 Performance Metrics

### ⏱️ Processing Times

**Typical processing times (per AFSC):**

| Stage | Min Time | Avg Time | Max Time | Bottleneck |
|-------|----------|----------|----------|------------|
| Preprocessing | <0.1s | <0.1s | <0.1s | No |
| LAiSER extraction | 2s | 3.5s | 5s | Yes |
| Quality filtering | <0.1s | <0.1s | <0.1s | No |
| LLM enhancement* | 1s | 2s | 3s | Yes (optional) |
| Deduplication | <0.1s | <0.1s | <0.1s | No |
| Neo4j write | 0.5s | 0.7s | 1s | No |
| **TOTAL** | **3s** | **6.3s** | **9.1s** | - |

*LLM Enhancement is optional and disabled by default

### 📉 Item Flow

**Reduction through pipeline:**

| Stage | Typical Count | Reduction % | Description |
|-------|---------------|-------------|-------------|
| LAiSER Extract | 20-30 | - | Raw skills from LAiSER |
| Quality Filter | 18-27 | ~10% | Remove noise, short items |
| LLM Enhance* | 25-40 | - | Add K/A items (optional) |
| Deduplication | 21-34 | ~15% | Remove near-duplicates |
| Final Output | 25-35 | - | Clean, canonical KSAs |

### 🎯 Accuracy Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| False Positive Rate | <1% | Near-duplicates |
| Extraction Recall | ~85% | vs manual review |
| Precision | ~90% | Relevant KSAs |

### 💾 Resource Usage

| Resource | Usage | Notes |
|----------|-------|-------|
| Memory Peak | ~200MB | Includes LAiSER + LLM libraries |
| CPU Cores | 1-2 cores | Parallelizable across AFSCs |
| Network (per AFSC) | ~50KB | Mostly API calls (LAiSER, Gemini) |
| Storage (per AFSC) | ~5KB | Neo4j node/relationship storage |

---

## 🔧 Module Documentation

### `preprocess.py`
**Purpose:** Cleans raw AFSC text from PDF sources

**Key function:** `clean_afsc_text(raw: str) -> str`

**Features:**
- Removes headers/footers/page numbers
- Fixes hyphenated line breaks
- Normalizes whitespace
- Preserves paragraph structure

### `extract_laiser.py`
**Purpose:** LAiSER integration for skill extraction with ESCO alignment

**Key functions:**
- `extract_ksa_items(clean_text: str) -> List[ItemDraft]`
- `_build_extractor() -> SkillExtractorRefactored | None`

**Features:**
- Skill extraction from job descriptions
- ESCO/OSN taxonomy alignment
- Confidence scoring
- Fallback to regex heuristics

### `quality_filter.py`
**Purpose:** Multi-stage filtering for quality control

**Key function:** `apply_quality_filter(items: List[ItemDraft], **kwargs) -> List[ItemDraft]`

**Filter stages:**
1. Length constraints (3-80 chars)
2. Domain relevance filtering
3. Canonical text mapping
4. Exact deduplication

### `enhance_llm.py`
**Purpose:** Optional LLM-based Knowledge/Ability generation

**Key functions:**
- `enhance_items_with_llm(afsc_code, afsc_text, items) -> List[ItemDraft]`
- `run_llm(prompt: str, provider: str, api_key: str) -> str`

**Supported providers:**
- Google Gemini (primary)
- OpenAI GPT
- Anthropic Claude
- HuggingFace

**Features:**
- Multi-provider support with automatic fallback
- Smart prompting with balancing hints
- Duplicate detection and filtering
- Output sanitization and parsing

### `dedupe.py`
**Purpose:** Fuzzy deduplication using hybrid similarity

**Key function:** `canonicalize_items(items: List[ItemDraft], **kwargs) -> List[ItemDraft]`

**Algorithm:**
- Hybrid similarity (60% Jaccard + 40% difflib)
- Threshold: 0.86 for near-duplicates
- ESCO-aware canonicalization
- Quality-based winner selection

### `graph_writer_v2.py`
**Purpose:** Neo4j persistence layer with idempotent MERGE operations

**Key function:** `upsert_afsc_and_items(session, afsc_code, items) -> Dict[str, int]`

**Features:**
- MERGE operations (idempotent upserts)
- Cypher query execution
- Relationship management
- AFSC ↔ KSA ↔ ESCO graph persistence

### `pipeline.py`
**Purpose:** Main orchestration module coordinating all stages

**Key functions:**
- `run_pipeline(afsc_code, afsc_raw_text, neo4j_session, **kwargs) -> Dict`
- `run_pipeline_demo(afsc_code, afsc_raw_text, **kwargs) -> Dict` (no DB writes)

**Features:**
- End-to-end orchestration
- Error handling and logging
- Summary statistics
- Demo mode for testing

---

## 🐛 Troubleshooting

### LAiSER API Errors

**Problem:** `Could not init: No module named 'laiser'`

**Solution:**
```bash
pip install laiser
# Ensure GEMINI_API_KEY is set
export GEMINI_API_KEY=your-key
```

**Fallback behavior:** If LAiSER fails, pipeline uses regex-based extraction automatically.

### Neo4j Connection Issues

**Problem:** `Failed to establish connection to Neo4j`

**Solutions:**
1. Verify credentials: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
2. Check network connectivity to Neo4j Aura
3. Ensure database name matches: `NEO4J_DATABASE=neo4j`

### Low Extraction Quality

**Problem:** Only extracting 5-10 items instead of 20-30

**Solutions:**
1. Verify `USE_LAISER=true`
2. Check `LAISER_ALIGN_TOPK` (recommend 25-30)
3. Review LAiSER logs for API errors
4. Verify Gemini API key is valid

### LLM Enhancement Not Working

**Problem:** Only 1-2 K/A items generated instead of 5-15

**Solutions:**
1. Check `USE_LLM_ENHANCER=true`
2. Verify API key for selected provider
3. Check `max_tokens` setting (should be 1024)
4. Review logs for API errors or safety filter triggers

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Test single AFSC extraction
python -m afsc_pipeline.cli process-afsc 1N0X1 path/to/text.txt

# Validate Neo4j schema
python -m afsc_pipeline.graph_writer_v2 --validate
```

---

## 📦 Dependencies

### Core Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| laiser | 0.1+ | Skill extraction |
| google-generativeai | 0.3+ | Gemini API |
| neo4j | 5.x | Graph database driver |
| streamlit | 1.40+ | Web interface |
| pypdf | 3.x | PDF text extraction |
| pandas | 2.x | Data manipulation |

### Optional Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| anthropic | 0.x | Claude API |
| openai | 1.x | GPT API |
| huggingface-hub | 0.x | HuggingFace models |

---

## 🎓 Key Design Decisions

### Why LAiSER + Gemini?
- **Integrated ESCO alignment**: Single API call extracts skills AND taxonomy IDs
- **Cost-effective**: Gemini Flash at ~$0.075 per 1M tokens
- **Reliable**: Built by GWU specifically for job description analysis

### Why Custom Deduplication (Not FAISS)?
- **Scale**: 20-50 items per AFSC (FAISS optimized for millions)
- **Explainability**: Hybrid similarity score (60% Jaccard + 40% difflib)
- **Performance**: <100ms per AFSC with full transparency

### Why Neo4j?
- **Relationship queries**: Natural fit for AFSC↔KSA↔ESCO mappings
- **Scalability**: Cloud-hosted (Aura) with automatic backups
- **Cypher queries**: Expressive pattern matching for skill analysis

### Why 5000 Character Input Limit?
- **Full context**: Most AFSCs are ~4000 characters
- **Negligible cost**: Only ~$0.0001 more per AFSC vs 2000 chars
- **Better quality**: Complete descriptions improve extraction accuracy

---

## 📝 Contributing

This is a GWU Data Science capstone project. For questions or collaboration:

- **GitHub Issues**: [Report bugs or request features](https://github.com/Kyleinexile/fall-2025-group6/issues)
- **Email**: Contact via GWU email

---

## 📄 License

MIT License

---

## 🙏 Acknowledgments

- **LAiSER**: GWU-developed skill extraction framework
- **ESCO**: European Skills, Competences, Qualifications and Occupations
- **Neo4j**: Graph database platform
- **Streamlit**: Interactive web application framework

---

## 📧 Contact

**Kyle Hall**  
📧 [kyle.hall@gwmail.gwu.edu](mailto:kyle.hall@gwmail.gwu.edu)  
🔗 [GitHub Repository](https://github.com/Kyleinexile/fall-2025-group6)

---

**Built with ❤️ at George Washington University**

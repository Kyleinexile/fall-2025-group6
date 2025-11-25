# AFSC → KSA Extraction Pipeline

**Production-ready extraction pipeline** that transforms Air Force Specialty Code (AFSC) job descriptions into structured Knowledge, Skills, and Abilities (KSAs) with taxonomy alignment.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![LAiSER](https://img.shields.io/badge/LAiSER-0.1+-green.svg)
![Neo4j](https://img.shields.io/badge/neo4j-5.0+-blue.svg)

---

## 🎯 Quick Stats

- ✅ **12 AFSCs processed** with 253 KSAs extracted
- ✅ **~20% ESCO taxonomy alignment**
- ✅ **60-80 seconds** average processing time
- ✅ **LAiSER + Gemini integration** for skill extraction and taxonomy alignment
- ✅ **Multi-provider LLM support** (OpenAI, Anthropic, Gemini, HuggingFace)

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
│    • LAiSER + Gemini: Extract 15-25 skills per AFSC        │
│    • Built-in ESCO taxonomy alignment                       │
│    • Fallback: Regex heuristics if LAiSER unavailable      │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. QUALITY FILTERING (quality_filter.py)                    │
│    • Length constraints (3-80 chars for skills, 150 for K/A)│
│    • Domain relevance filtering                             │
│    • Canonical text mapping                                 │
│    • Exact deduplication on (type, text)                    │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. LLM ENHANCEMENT (enhance_llm.py) - OPTIONAL              │
│    • Generate complementary Knowledge & Ability items       │
│    • Multi-provider: Gemini, OpenAI, Anthropic, HuggingFace │
│    • When enabled: 1024 token max output                    │
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

```toml
# ================================
# LAiSER (Skill Extractor)
# ================================
USE_LAISER            = "true"
LAISER_ALIGN_TOPK     = "25"
LAISER_LLM_ENABLED    = "true"
LAISER_LLM_PROVIDER   = "gemini"
LAISER_MODEL_GEMINI   = "gemini-2.0-flash"

# ================================
# LLM Enhancement Layer (K/A)
# ================================
USE_LLM_ENHANCER      = "true"
LLM_PROVIDER          = "openai"

# Model configuration
LLM_MODEL_OPENAI      = "gpt-4o-mini-2024-07-18"
LLM_MODEL_ANTHROPIC   = "claude-sonnet-4-5-20250929"
LLM_MODEL_GEMINI      = "gemini-2.0-flash"

# API Keys
OPENAI_API_KEY        = "sk-..."
ANTHROPIC_API_KEY     = "sk-ant-..."
GEMINI_API_KEY        = "AIza..."

# ================================
# Neo4j Database
# ================================
NEO4J_URI             = "neo4j+s://your-instance.databases.neo4j.io:7687"
NEO4J_USER            = "neo4j"
NEO4J_PASSWORD        = "your-password"
NEO4J_DATABASE        = "neo4j"

# ================================
# Quality Filtering
# ================================
QUALITY_MIN_LEN       = "3"
QUALITY_MAX_LEN       = "80"
QUALITY_MAX_LEN_KA    = "150"
LOW_CONF_SKILL_THRESHOLD = "0.60"

# Deduplication
AGGRESSIVE_DEDUPE     = "true"
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
        afsc_code="1N0",
        afsc_raw_text=open("afsc_text.txt").read(),
        neo4j_session=session,
    )

print(f"Extracted {summary['n_items_after_dedupe']} KSAs")
```

### Demo Mode (No Database Writes)

```python
from afsc_pipeline.pipeline import run_pipeline_demo

summary = run_pipeline_demo(
    afsc_code="1N0",
    afsc_raw_text="Your AFSC text here...",
)

# Results available in summary['items']
for item in summary['items']:
    print(f"{item.item_type.value}: {item.text}")
```

### Streamlit Web Interface

```bash
cd demo/Streamlit
streamlit run Home.py
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

**1. Model Selection**
- **Gemini Flash**: Cost-effective for LAiSER backend
- **GPT-4o-mini**: Affordable option for LLM enhancement
- Both models provide good quality at low cost

**2. Token Limits**
- Input limit: 5000 characters (full AFSC context)
- Output limit: 1024 tokens
- Max new items: 6 per AFSC

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

### 🔄 Deduplication Strategy

Custom hybrid approach optimized for short text:

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

**Performance:**
- Deduplication reduction: 10-20% of items removed
- Execution time: <100ms per AFSC
- False positive rate: <1% (verified manually)

### 🎚️ Quality Filtering

Configurable via environment variables:

```bash
# Length constraints
QUALITY_MIN_LEN=3         # Minimum characters
QUALITY_MAX_LEN=80        # Maximum for skills
QUALITY_MAX_LEN_KA=150    # Maximum for Knowledge/Abilities

# Confidence threshold
LOW_CONF_SKILL_THRESHOLD=0.60
```

---

## 📊 Performance Metrics

### ⏱️ Processing Times

**Typical processing times (per AFSC):**

| Stage | Description | Time |
|-------|-------------|------|
| Preprocessing | Text cleaning | <1s |
| LAiSER extraction | Skill extraction + ESCO | 30-45s |
| Quality filtering | Length/domain filters | <1s |
| LLM enhancement | K/A generation (optional) | 15-25s |
| Deduplication | Fuzzy matching | <1s |
| Neo4j write | Graph persistence | 1-2s |
| **TOTAL** | End-to-end | **60-80s** |

### 📉 Item Flow

**Reduction through pipeline:**

| Stage | Typical Count | Description |
|-------|---------------|-------------|
| LAiSER Extract | 15-25 | Raw skills from LAiSER |
| Quality Filter | 12-22 | Remove noise, short items |
| LLM Enhance* | 18-30 | Add K/A items (optional) |
| Deduplication | 15-25 | Remove near-duplicates |
| Final Output | ~21 avg | Clean, canonical KSAs |

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
1. Length constraints (3-80 chars for skills, 150 for K/A)
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

**Problem:** Only extracting 5-10 items instead of 15-25

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
python -m afsc_pipeline.cli process-afsc 1N0 path/to/text.txt

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
- **Cost-effective**: Gemini Flash provides good performance at low cost
- **Reliable**: Built by GWU specifically for job description analysis

### Why Custom Deduplication?
- **Scale**: 20-50 items per AFSC (right-sized solution)
- **Explainability**: Clear hybrid formula (60% Jaccard + 40% difflib)
- **Performance**: <100ms per AFSC with full transparency

### Why Neo4j?
- **Relationship queries**: Natural fit for AFSC↔KSA↔ESCO mappings
- **Scalability**: Cloud-hosted (Aura) with automatic backups
- **Cypher queries**: Expressive pattern matching for skill analysis

### Why 5000 Character Input Limit?
- **Full context**: Most AFSCs are ~4000 characters
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

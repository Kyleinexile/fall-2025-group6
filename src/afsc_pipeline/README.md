# AFSC → KSA Extraction Pipeline

Production-ready extraction pipeline that transforms Air Force Specialty Code (AFSC) job descriptions into structured Knowledge, Skills, and Abilities (KSAs) with taxonomy alignment.

## Quick Stats

- ✅ **12 AFSCs processed** with 330+ KSAs extracted
- ✅ **~$0.005 per AFSC** processing cost (LAiSER-only mode)
- ✅ **3.2 seconds** average processing time
- ✅ **LAiSER + Gemini integration** for skill extraction and taxonomy alignment

## Architecture Overview

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
│    • When enabled: Gemini Flash, 512 token max             │
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

## Installation

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
GEOINT_BIAS=false

# Deduplication
AGGRESSIVE_DEDUPE=true
```

## Usage

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

## Configuration Guide

### Cost Optimization

**Default configuration prioritizes cost efficiency:**

1. **LLM Enhancement Disabled** (`USE_LLM_ENHANCER=false`)
   - LAiSER extraction alone achieves coverage goals
   - Enable only when Knowledge/Ability items are required

2. **Gemini Flash Model** (when LLM enabled)
   - Cheapest available option (~$0.075 per 1M input tokens)
   - Alternative: `gpt-4o-mini` (~$0.15 per 1M tokens)

3. **Token Limits**
   - Input limit: 5000 characters (full AFSC context)
   - Output limit: 512 tokens
   - Max new items: 6 per AFSC

**Cost breakdown per AFSC:**
- LAiSER-only: ~$0.005
- With LLM enhancement: ~$0.005-0.010 (Gemini Flash)

### LAiSER Configuration

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

### Deduplication Strategy

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
- Dataset scale: 20-50 items per AFSC
- Explainability: Simple similarity scores
- Performance: <100ms per AFSC

### Quality Filtering

Configurable via environment variables:

```bash
# Strict mode: Require ESCO IDs for low-confidence skills
STRICT_SKILL_FILTER=false

# Domain focus: Prefer GEOINT-related skills
GEOINT_BIAS=false

# Confidence threshold for strict filtering
LOW_CONF_SKILL_THRESHOLD=0.60
```

**Filter stages:**
1. Length validation (3-80 chars)
2. Banned phrase removal
3. Canonical text mapping
4. Exact deduplication

## Troubleshooting

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

## Performance Metrics

**Typical processing times (per AFSC):**
- Preprocessing: <0.1s
- LAiSER extraction: 2-5s
- Quality filtering: <0.1s
- LLM enhancement: 1-3s (if enabled)
- Deduplication: <0.1s
- Neo4j write: 0.5-1s
- **Total: 3-8 seconds per AFSC**

**Resource usage:**
- Memory: ~200MB peak
- CPU: 1-2 cores
- Network: ~50KB per AFSC (API calls)

## Testing

```bash
# Run unit tests
pytest tests/

# Test single AFSC extraction
python -m afsc_pipeline.cli process-afsc 1N0X1 path/to/text.txt

# Validate Neo4j schema
python -m afsc_pipeline.graph_writer_v2 --validate
```

## Module Documentation

### `preprocess.py`
Cleans raw AFSC text from PDF sources. Removes headers/footers, fixes hyphenation, normalizes whitespace.

**Key function:** `clean_afsc_text(raw: str) -> str`

### `extract_laiser.py`
LAiSER integration for skill extraction with ESCO alignment. Includes fallback heuristics.

**Key functions:**
- `extract_ksa_items(clean_text: str) -> List[ItemDraft]`
- `_build_extractor() -> SkillExtractorRefactored | None`

### `quality_filter.py`
Multi-stage filtering: length, domain relevance, canonical mapping, exact deduplication.

**Key function:** `apply_quality_filter(items: List[ItemDraft], **kwargs) -> List[ItemDraft]`

### `enhance_llm.py`
Optional LLM-based Knowledge/Ability generation with multi-provider support.

**Key functions:**
- `enhance_items_with_llm(afsc_code, afsc_text, items) -> List[ItemDraft]`
- `run_llm(prompt: str, provider: str, api_key: str) -> str`

### `dedupe.py`
Fuzzy deduplication using hybrid similarity (Jaccard + difflib). ESCO-aware canonicalization.

**Key function:** `canonicalize_items(items: List[ItemDraft], **kwargs) -> List[ItemDraft]`

### `graph_writer_v2.py`
Neo4j persistence layer with idempotent MERGE operations. Manages AFSC, KSA, and ESCO nodes.

**Key function:** `upsert_afsc_and_items(session, afsc_code, items) -> Dict[str, int]`

### `pipeline.py`
Main orchestration module coordinating all stages.

**Key functions:**
- `run_pipeline(afsc_code, afsc_raw_text, neo4j_session, **kwargs) -> Dict`
- `run_pipeline_demo(afsc_code, afsc_raw_text, **kwargs) -> Dict` (no DB writes)

## Contributing

This is a GWU Data Science capstone project. For questions or collaboration:

- **GitHub Issues**: [Report bugs or request features](https://github.com/Kyleinexile/fall-2025-group6/issues)
- **Email**: Contact via GWU email

## License

[MIT License]

## Acknowledgments

- **LAiSER**: GWU-developed skill extraction framework
- **ESCO**: European Skills, Competences, Qualifications and Occupations
- **Neo4j**: Graph database platform
- **Streamlit**: Interactive web application framework

## Citation

If you use this pipeline in your research, please cite:

```bibtex
@misc{afsc_ksa_pipeline,
  title={AFSC to KSA Extraction Pipeline},
  author={Kyle [Last Name] and Team},
  year={2025},
  institution={George Washington University},
  howpublished={\url{https://github.com/Kyleinexile/fall-2025-group6}}
}
```

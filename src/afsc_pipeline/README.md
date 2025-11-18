# AFSC Pipeline (`src/afsc_pipeline/`)

This directory implements the full end-to-end **AFSC → KSA** extraction pipeline used by:

- The **Admin Tools** ingestion interface
- The **Try It Yourself** sandbox mode
- The core backend supporting the Streamlit application

The pipeline converts unstructured AFOCD/AFECD text into structured **Knowledge**, **Skill**, and **Ability** items and persists them into a **Neo4j graph** using idempotent upserts.

---

## ⭐ High-Level Architecture
```
Raw AFSC Text
     │
     ▼
1. Preprocessing
   (cleanup, fix formatting)
     │
     ▼
2. Skill Extraction (LAiSER)
   (gets action-oriented Skills with ESCO alignment)
     │
     ▼
3. LLM Enhancement
   (adds Knowledge + Abilities)
     │
     ▼
4. Quality Filtering
   (removes noise, short items, off-topic items)
     │
     ▼
5. Fuzzy Deduplication
   (merges near-duplicates using hybrid similarity)
     │
     ▼
6. Neo4j Graph Writer
   (creates/updates AFSC + KSA nodes)
```

The output is a clean, reusable, searchable KSA inventory for each AFSC.

---

## 📋 Module-by-Module Reference

### `types.py` — Core Data Structures
Defines the canonical data types used across the pipeline.

**`ItemType` Enum:**
- `KNOWLEDGE`
- `ABILITY`
- `SKILL`

**`ItemDraft` Class:**

Lightweight extraction-stage representation:
- `text` - The item description
- `item_type` - Knowledge, Skill, or Ability (enum)
- `confidence` - Extraction confidence score (0.0-1.0)
- `source` - Origin (e.g., `laiser-gemini`, `llm-openai`)
- `esco_id` - Optional taxonomy alignment code

Used uniformly by LAiSER, LLM outputs, quality filtering, and deduplication stages.

**`KsaItem` Class:**

Rich final-stage representation for UI/database:
- `name` - Human-readable text
- `type` - Knowledge, Skill, or Ability (string)
- `evidence` - Optional supporting text
- `confidence` - Score
- `esco_id` - Taxonomy code
- `canonical_key` - Deduplication key
- `meta` - Additional metadata

**`AfscDoc` Class:**

Container for AFSC documents:
- `code` - AFSC identifier
- `title` - Specialty name
- `raw_text` - Original unprocessed text
- `clean_text` - Normalized text for extraction

**`RunReport` Class:**

Pipeline execution summary:
- `afsc_code`, `afsc_title`
- `counts_by_type` - Distribution of K/S/A items
- `created_items`, `updated_items`, `created_edges` - Database statistics
- `warnings`, `artifacts` - Debugging information

---

### `config.py` — Configuration & Environment Settings

Manages:
- Neo4j credentials (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- Quality thresholds (`MIN_LEN`, `MAX_LEN`, `LOW_CONF_SKILL_THRESHOLD`)
- LLM provider configuration (currently supports Gemini for LAiSER)
- Feature toggles (`USE_LAISER`, `USE_LLM_ENHANCER`)
- Local vs deployment overrides (via environment variables or `secrets.toml`)

All configuration is environment-driven, allowing the same code to run in:
- Local development
- GitHub Codespaces
- Streamlit Cloud
- Containerized deployments

---

### `preprocess.py` — Text Cleaning & Normalization

Prepares raw AFOCD/AFECD text by:

- Removing page headers, footers, and numbering
- Fixing hyphenation and broken lines (e.g., "some-\nthing" → "something")
- Normalizing whitespace and line breaks
- Stripping markdown tables and code fences
- Removing classification headers (AFECD, DAFECD, AFI, etc.)
- Producing consistent paragraphs for LAiSER and LLM inputs

**Function:** `clean_afsc_text(raw: str) -> str`

Preprocessing dramatically improves extraction accuracy by providing clean, normalized input text.

---

### `extract_laiser.py` — LAiSER Skill Extraction

Runs LAiSER's NLP pipeline to identify **Skill-type** items with built-in ESCO alignment:

**Features:**
- Action-oriented verb-object phrases (e.g., "conduct target analysis")
- Domain-specific technical competencies
- Confidence-scored outputs (0.0-1.0 range)
- **Built-in alignment to ESCO/OSN taxonomy** (LAiSER provides ESCO codes directly)
- Configurable via `USE_LAISER`, `LAISER_ALIGN_TOPK`, `LAISER_LLM_PROVIDER`

**Current Configuration:**
- Provider: Gemini (`gemini-2.0-flash`)
- Top-K alignment: 25 skills per AFSC
- Falls back to regex-based heuristics if LAiSER unavailable

**Outputs:** List of `ItemDraft(SKILL)` objects with ESCO IDs when available.

LAiSER provides the backbone of concrete, task-oriented skills with standardized taxonomy codes (50-60% ESCO coverage).

---

### `enhance_llm.py` — LLM-Based Knowledge & Ability Generation

Adds conceptual depth via multi-provider LLM generation.

**Supported Providers:**
- **OpenAI** (`gpt-4o-mini-2024-07-18`)
- **Anthropic** (`claude-sonnet-4-5-20250929`)
- **Google Gemini** (`gemini-2.0-flash`)
- **HuggingFace** (`meta-llama/Llama-3.2-3B-Instruct`)

**Features:**
- Strict 120-character bullet generation
- Enforces exact surface forms ("Knowledge of …", "Ability to …")
- Balances output based on existing item distribution
- Rejects duplicates and paraphrases
- Sanitizes format (bullets, punctuation, casing)
- Provides **runtime override** for Try It Yourself (user-provided API keys)
- Includes heuristic fallback if all LLMs fail

**Provider Fallback:**
- OpenAI ↔ Gemini (mutual fallback)
- Anthropic → heuristics
- HuggingFace → heuristics

**Outputs:** List of `ItemDraft(KNOWLEDGE)` and `ItemDraft(ABILITY)` entries with confidence fixed at 0.70.

**Typical Results:** 1-6 Knowledge/Ability items per AFSC (varies by provider).

---

### `quality_filter.py` — Structural & Confidence Filtering

Ensures clean, valid items through multiple quality gates:

**Filtering Rules:**
- Remove items shorter than `MIN_LEN` characters (default: 3)
- Remove items longer than `MAX_LEN` characters (default: 80)
- Remove items in BANNED list (observed noise from extraction)
- Apply canonicalization rules (e.g., "imagery analysis" → "imagery exploitation")
- Perform exact-text deduplication on `(item_type, normalized_text)` pairs

**Optional Filters (disabled by default):**
- `STRICT_SKILL_FILTER`: Require ESCO ID for low-confidence skills
- `GEOINT_BIAS`: Require GEOINT domain keywords for low-confidence skills

**Text Normalization:**
- Lowercase and trim
- Strip punctuation
- Collapse whitespace
- Apply canonical phrase mappings

**Function:** `apply_quality_filter(items, strict_skill_filter=False, geoint_bias=False)`

Produces a high-quality candidate set before semantic deduplication.

---

### `dedupe.py` — Fuzzy Deduplication & Canonicalization

Merges near-duplicate items using hybrid text similarity (NOT embedding-based).

**Algorithm:**
1. Partition items by `ItemType` (compare only like types)
2. Normalize text: lowercase, remove punctuation, collapse whitespace
3. Compute hybrid similarity for each pair:
   - **60% Token Jaccard** (set overlap)
   - **40% Character difflib** (sequence matching)
4. Cluster items with similarity ≥ 0.86 threshold
5. Select best representative per cluster:
   - Prefer ESCO-tagged items
   - Prefer higher confidence
   - Prefer LAiSER-sourced items
   - Prefer longer text (tiebreaker)
6. Lift ESCO IDs from cluster members to winner if needed

**Key Parameters:**
- `similarity_threshold`: 0.86 (default)
- `min_text_len`: 4 characters (skip very short items)

**Function:** `canonicalize_items(items, similarity_threshold=0.86)`

**Example:**
- "Knowledge of intelligence cycle" + "Knowledge of intelligence cycle fundamentals" → merged
- "conduct analysis" + "perform analysis" → merged (high token overlap)

**Result:** Non-redundant KSA inventory (typically 10-20% reduction in item count).

**Note:** This module does NOT use FAISS or Sentence-Transformers embeddings. The similarity metric is purely text-based (Jaccard + difflib).

---

### `esco_mapper.py` — Optional ESCO/OSN Skill Taxonomy Mapping

**Status: Optional - Not used in main pipeline**

LAiSER provides built-in ESCO alignment, so this module is primarily for:
- Legacy workflows
- Non-LAiSER extraction methods
- Additional enrichment of LLM-generated items

**If used, it provides:**
- Fuzzy matching against local ESCO catalog CSV
- Hybrid similarity scoring (same algorithm as dedupe.py)
- Type-specific thresholds:
  - Skills: 0.90
  - Knowledge: 0.92
  - Abilities: 0.90
- Strips "Knowledge of" / "Ability to" prefixes before matching

**Function:** `map_esco_ids(items) -> List[ItemDraft]`

**Catalog:** `src/Data/esco/esco_skills.csv` (expected columns: `esco_id`, `label`, `alt_labels`)

---

### `graph_writer_v2.py` — Neo4j Graph Persistence

Handles all database writes using idempotent MERGE operations.

**Schema:**

**Nodes:**
- `AFSC {code, title, family, created_at, updated_at}`
- `KSA {content_sig, text, type, source, confidence, first_seen, last_seen}`
- `SourceDoc {title, date, created_at}`
- `ESCOSkill {esco_id, label, created_at}`

**Relationships:**
- `(AFSC)-[:REQUIRES {confidence, type}]->(KSA)`
- `(KSA)-[:EXTRACTED_FROM {evidence, section}]->(SourceDoc)`
- `(KSA)-[:ALIGNS_TO {score}]->(ESCOSkill)`

**Key Features:**
- Generates `content_sig` (MD5 hash of text, 16 chars) as KSA node key
- All operations use `MERGE` for idempotency
- Supports bulk ingestion
- Returns aggregate statistics (nodes_created, relationships_created, properties_set)

**Functions:**
- `upsert_afsc_and_items(session, afsc_code, items)` - Main write function
- `ensure_constraints(session)` - Create uniqueness constraints (idempotent)

**Note:** `content_sig` is computed during graph writes, NOT stored in `ItemDraft` during pipeline processing.

---

### `audit.py` — Pipeline Event Logging

Structured JSON logging for pipeline runs.

**Logs:**
- AFSC code processed
- Number of items written
- Whether fallback was used
- Errors encountered
- Processing duration (ms)
- Database write statistics

**Function:** `log_extract_event(afsc_code, n_items, used_fallback, errors, duration_ms, write_stats)`

**Output:** JSON lines to stdout (safe for Streamlit/CLI logs)

Used for debugging, quality control, and performance monitoring.

---

### `pipeline.py` — Orchestrator

Primary entrypoint for end-to-end extraction.

**Main Function:**
```python
run_pipeline(
    afsc_code: str,
    afsc_raw_text: str,
    neo4j_session: Optional[Any] = None,
    *,
    min_confidence: float = 0.0,
    keep_types: bool = True,
    strict_skill_filter: bool = False,
    geoint_bias: bool = False,
    aggressive_dedupe: bool = True,
    write_to_db: bool = True
) -> Dict[str, Any]
```

**Execution Flow:**
1. **Preprocess** raw text → clean narrative
2. **Extract** skills via LAiSER (or fallback heuristics)
3. **Enhance** with LLM (if `USE_LLM_ENHANCER=true`)
4. **Filter** by confidence and quality rules
5. **Deduplicate** using fuzzy similarity (if `aggressive_dedupe=true`)
6. **Write** to Neo4j (if `write_to_db=true` and session provided)
7. **Log** audit event (if `write_to_db=true`)
8. **Return** detailed summary dict

**Demo Mode Function:**
```python
run_pipeline_demo(
    afsc_code: str,
    afsc_raw_text: str,
    **kwargs
) -> Dict[str, Any]
```
- Forces `write_to_db=False` and `neo4j_session=None`
- Used by Try It Yourself page
- Returns same summary format for UI display

**Return Value:**
```python
{
    "afsc": str,
    "n_items_raw": int,
    "n_items_after_filters": int,
    "n_items_after_dedupe": int,
    "esco_tagged_count": int,
    "used_fallback": bool,
    "errors": List[str],
    "duration_ms": int,
    "write_stats": Dict[str, int],
    "items": List[ItemDraft]
}
```

---

## 📄 Data Flow Summary
```
                    preprocess.py
    Raw AFSC Text  ──────────────▶ Clean doc
                                  │
                                  ▼
                       extract_laiser.py
                     Skill candidates (with ESCO)
                                  │
                                  ▼
                        enhance_llm.py
            Knowledge + Ability candidates
                                  │
                                  ▼
                      quality_filter.py
                  Confidence + format checks
                                  │
                                  ▼
                            dedupe.py
              Fuzzy similarity (Jaccard + difflib)
                                  │
                                  ▼
                      graph_writer_v2.py
                 Neo4j MERGE nodes + edges
```

**Note:** ESCO mapping happens during LAiSER extraction (built-in), not as a separate step.

---

## 🔗 Integration with Streamlit App

This pipeline powers two major interfaces:

### Admin Tools (Full Pipeline + Database Writes)
- Upload raw AFSC text
- Run full ingestion with all pipeline stages
- **Writes results to Neo4j**
- Delete AFSCs from database
- Inspect audit logs
- View extraction statistics

### Try It Yourself (Sandbox Mode)
- User chooses LLM provider (OpenAI / Anthropic / Gemini / HuggingFace)
- User supplies personal API key
- Runs full extraction pipeline
- **Does not write to database** (`write_to_db=False`)
- Displays K/S/A results interactively
- Download results as CSV

---

## ⚙️ Configuration

### Environment Variables

**LAiSER Configuration:**
```bash
USE_LAISER="true"
LAISER_LLM_PROVIDER="gemini"
LAISER_GEMINI_API_KEY="your-key"
LAISER_ALIGN_TOPK="25"
```

**LLM Enhancement:**
```bash
USE_LLM_ENHANCER="true"
LLM_PROVIDER="openai"  # or anthropic, gemini, huggingface
OPENAI_API_KEY="your-key"
ANTHROPIC_API_KEY="your-key"
GEMINI_API_KEY="your-key"
HF_TOKEN="your-token"
```

**Model Names:**
```bash
LLM_MODEL_OPENAI="gpt-4o-mini-2024-07-18"
LLM_MODEL_ANTHROPIC="claude-sonnet-4-5-20250929"
LLM_MODEL_GEMINI="gemini-2.0-flash"
LLM_MODEL_HUGGINGFACE="meta-llama/Llama-3.2-3B-Instruct"
```

**Neo4j:**
```bash
NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your-password"
NEO4J_DATABASE="neo4j"
```

**Quality Filters (Optional):**
```bash
QUALITY_MIN_LEN="3"
QUALITY_MAX_LEN="80"
LOW_CONF_SKILL_THRESHOLD="0.60"
STRICT_SKILL_FILTER="false"
GEOINT_BIAS="false"
```

### Streamlit Secrets (`secrets.toml`)

For Streamlit Cloud deployment, configure secrets in the dashboard:
```toml
[secrets]
USE_LAISER = "true"
LAISER_GEMINI_API_KEY = "your-key"
USE_LLM_ENHANCER = "true"
OPENAI_API_KEY = "your-key"
NEO4J_URI = "neo4j+s://..."
NEO4J_PASSWORD = "your-password"
```

---

## ✅ Summary

This pipeline implements a robust, modular, production-grade AFSC → KSA extraction framework:

- ✅ **LAiSER skill extraction** with built-in ESCO/OSN taxonomy alignment (50-60% coverage)
- ✅ **Multi-provider LLM enhancement** (OpenAI, Anthropic, Gemini, HuggingFace) for Knowledge/Ability items
- ✅ **Quality filtering** with configurable domain-specific rules
- ✅ **Fuzzy deduplication** using hybrid text similarity (Jaccard + difflib, threshold 0.86)
- ✅ **Idempotent Neo4j graph persistence** with comprehensive schema
- ✅ **Full Streamlit integration** (Admin + Demo modes with BYO-API support)
- ✅ **Structured audit logging** for debugging and quality control

**Typical Output:** 25-30 KSAs per AFSC with alignment to 2,217+ standardized skills from the Open Skills Network.

---

## 📚 Additional Resources

- **Open Skills Network (OSN)**: [Learn Work Ecosystem Library](https://learnworkecosystemlibrary.com/initiatives/open-skills-network-osn/)
- **LAiSER Framework**: [GitHub - LAiSER Extract Module](https://github.com/LAiSER-Software/extract-module)
- **ESCO Framework**: [European Skills, Competences, Qualifications and Occupations](https://esco.ec.europa.eu/)
- **Neo4j Graph Database**: [Neo4j Documentation](https://neo4j.com/docs/)

---

## 🐛 Known Issues & Limitations

1. **Intelligence Domain Bias**: Fallback heuristics are optimized for intelligence/GEOINT AFSCs
2. **LLM Variability**: Knowledge/Ability counts vary by provider (1-6 items instead of consistent 3+3)
3. **Gemini Rate Limits**: Free tier limited to 2 requests/minute (requires ~40s wait between runs)
4. **ESCO Coverage**: Currently 50-60% of skills aligned to taxonomy (target: 70%+)
5. **No Page-Level Provenance**: Source tracking at document/section level only

---

## 🔮 Future Enhancements

- SME-driven KSA ranking and weighting
- Expanded AFSC coverage (all USAF enlisted + officer specialties)
- Integration with Navy/Army/Marine Corps MOS systems
- O*NET-based military-to-civilian occupation mapping
- Skill gap analysis tool (AFSC requirements vs civilian job postings)
- Longitudinal tracking of AFSC requirement changes over time

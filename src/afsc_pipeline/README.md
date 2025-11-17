# AFSC Pipeline (`src/afsc_pipeline/`)

This directory implements the full end-to-end **AFSC → KSA** extraction pipeline used by:

- The **Admin Tools** ingestion interface
- The **Try It Yourself** sandbox mode
- The core backend supporting the Streamlit application

The pipeline converts unstructured AFOCD/AFECD text into structured **Knowledge**, **Skill**, and **Ability** items and persists them into a **Neo4j graph** using idempotent upserts.

---

## ⭐ High-Level Architecture
Raw AFSC Text
     │
     ▼
1. Preprocessing
   (cleanup, fix formatting)
     │
     ▼
2. Skill Extraction (LAiSER)
   (gets action-oriented Skills)
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
5. Semantic Deduplication
   (merges near-duplicates)
     │
     ▼
6. ESCO/OSN Mapping
   (optional taxonomy alignment)
     │
     ▼
7. Neo4j Graph Writer
   (creates/updates AFSC + KSA nodes)


The output is a clean, reusable, searchable KSA inventory for each AFSC.

---

## 📁 Module-by-Module Reference

### `types.py` — Core Data Structures
Defines the canonical data types used across the pipeline.

**`ItemType` Enum:**
- `KNOWLEDGE`
- `ABILITY`
- `SKILL`

**`ItemDraft` Class:**

Encapsulates any extracted item:
- `text` - The item description
- `item_type` - Knowledge, Skill, or Ability
- `confidence` - Extraction confidence score (0.0-1.0)
- `source` - Origin (e.g., `laiser`, `llm-openai`)
- `esco_id` - Optional taxonomy alignment code

Used uniformly by LAiSER, LLM outputs, and ESCO mapping.

---

### `config.py` — Configuration & Environment Settings

Manages:
- Neo4j credentials  
- Thresholds (confidence, similarity)  
- LLM provider settings  
- Model names  
- Feature toggles (`USE_LAISER`)  
- Local vs deployment overrides (via `secrets.toml`)

This ensures reproducible pipeline behavior across local development and Streamlit Cloud.

---

### `preprocess.py` — Text Cleaning & Normalization

This module prepares raw AFOCD/AFECD text by:

- Removing page headers, footers, and numbering  
- Fixing hyphenation and broken lines  
- Normalizing whitespace  
- Cleaning bullet structures  
- Producing consistent paragraphs for LAiSER and LLM inputs  

Preprocessing dramatically improves extraction accuracy.

---

### `extract_laiser.py` — LAiSER Skill Extraction

Runs LAiSER's NLP pipeline to identify **Skill-type** items:

- Verb–object action phrases  
- Technical noun phrases  
- Confidence-scored outputs  
- Alignment to Open Skills Network (OSN) taxonomy

Outputs are wrapped as `ItemDraft(SKILL)` objects.

LAiSER provides the backbone of concrete, task-oriented skills with standardized taxonomy codes.

---

### `enhance_llm.py` — LLM-Based Knowledge & Ability Generation

Adds conceptual depth via LLM generation using:

- **OpenAI** (GPT-4o-mini)  
- **Anthropic** (Claude 3.5 Sonnet)  
- **Google Gemini** (Gemini 2.0 Flash)

**Features:**

- Strict 120-character bullet generation  
- Enforces exact surface forms ("Knowledge of …", "Ability to …")  
- Balances output depending on missing item types  
- Rejects duplicates and paraphrases  
- Sanitizes format (bullets, punctuation, casing)  
- Provides **runtime override** for Try It Yourself (provider + API key)  
- Includes heuristic fallback if all LLMs fail  

**Outputs:** Clean `ItemDraft(KNOWLEDGE)` and `ItemDraft(ABILITY)` entries.

---

### `quality_filter.py` — Structural & Confidence Filtering

Ensures clean, valid items by:

- Removing low-confidence Skills  
- Rejecting malformed or generic items  
- Normalizing punctuation & formatting  
- Enforcing proper K/A/S type rules  
- Performing initial exact-text deduplication  

Produces a high-quality candidate set before semantic merging.

---

### `dedupe.py` — Semantic Deduplication

Uses Sentence-Transformers + FAISS to merge similar items:

- Embedding-based similarity  
- Cluster items above threshold (≈ 0.83 cosine similarity)  
- Select the strongest representative  
- Prevents "Knowledge of X" vs "Knowledge of X operations" duplicates  

Ensures each AFSC receives a non-redundant KSA inventory.

---

### `esco_mapper.py` — Optional ESCO/OSN Skill Taxonomy Mapping

Attempts to map each item to **ESCO/OSN skill IDs** using:

- Embedding similarity  
- Ontology-based heuristics  
- Confidence scoring  

Adds interoperability with HR systems and labor market tools.

**Taxonomy Reference:** [LAiSER OSN Taxonomy (2,217+ skills)](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)

---

### `graph_writer_v2.py` — Neo4j Graph Persistence

Handles all database writes:

**Creates or merges:**
- `(:AFSC {code})` nodes
- `(:KSA {text, type})` nodes

**Attaches relationships:**
- `(:AFSC)-[:REQUIRES]->(:KSA)`
- `(:KSA)-[:ALIGNS_TO]->(:ESCOSkill)` (when taxonomy mapped)

**Features:**
- Cleans up old relationships on re-ingest  
- Uses `MERGE` for idempotency  
- Supports bulk ingestion  

This module is responsible for maintaining the authoritative AFSC → KSA graph.

---

### `audit.py` — Pipeline Artifacts & QC Reporting

Generates:

- LLM raw output  
- Filtered items  
- Deduplication merge logs  
- ESCO mapping diagnostics  
- Pipeline statistics (counts by type, confidence distribution)

Used in the Admin Tools page for inspection & debugging.

---

### `pipeline.py` — Orchestrator

Primary entrypoint:
```python
run_pipeline(
    afsc_code: str,
    text: str,
    write_to_db: bool = True
)
```

**Executes the full chain:**

1. Preprocessing
2. LAiSER extraction
3. LLM enhancement
4. Quality filtering
5. Semantic dedupe
6. ESCO/OSN mapping
7. Neo4j write (if enabled)

**Supports:**
- Bulk JSONL ingestion
- Sandbox mode (`write_to_db=False`) for Try It Yourself
- Returns a detailed report for the Streamlit UI

---

## 🔧 Development Tooling

### `scripts/try_pipeline.py`

Simple standalone runner for local development:
```bash
python src/afsc_pipeline/scripts/try_pipeline.py "<AFSC code>" "<raw text>"
```

Useful for testing extraction logic without Neo4j or Streamlit.

---

## 🔄 Data Flow Summary
```
                    preprocess.py
    Raw AFSC Text  ──────────▶ Clean doc
                                  │
                                  ▼
                       extract_laiser.py
                         Skill candidates
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
                 Semantic merging (FAISS)
                                  │
                                  ▼
                        esco_mapper.py
                   (optional ESCO mapping)
                                  │
                                  ▼
                      graph_writer_v2.py
                 Neo4j MERGE nodes + edges
```

---

## 🔒 Integration with Streamlit App

This pipeline powers two major interfaces:

### Admin Tools
- Upload raw AFSC text
- Run full ingestion
- Delete AFSCs
- Inspect audit logs
- **Writes results to Neo4j**

### Try It Yourself
- User chooses provider (OpenAI / Anthropic / Gemini)
- User supplies personal API key
- Runs full extraction pipeline
- **Does not write to the real database**
- Displays K/S/A results interactively
- Download results as CSV

---

## ✅ Summary

This pipeline implements a robust, modular, production-grade AFSC → KSA extraction framework incorporating:

- ✅ LAiSER skill extraction with OSN taxonomy alignment
- ✅ Multi-provider LLM enhancement (OpenAI, Anthropic, Gemini)
- ✅ Structured QC + semantic deduplication
- ✅ Optional ESCO/OSN taxonomy mapping
- ✅ Scalable Neo4j graph persistence
- ✅ Full Streamlit integration (Admin + Demo modes)

It forms the operational backbone of the AFSC KSA analysis application, extracting **25-30 KSAs per AFSC** with taxonomy alignment to 2,217+ standardized skills.

---

## 📚 Additional Resources

- **OSN Taxonomy**: [Open Skills Network](https://learnworkecosystemlibrary.com/initiatives/open-skills-network-osn/)
- **LAiSER Reference**: [GitHub - LAiSER Extract Module](https://github.com/LAiSER-Software/extract-module)
- **ESCO Framework**: [European Skills, Competences, Qualifications and Occupations](https://esco.ec.europa.eu/)

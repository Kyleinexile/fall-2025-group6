# USAF AFSC KSA Extraction Framework
_Fall 2025 — Group 6 Capstone_

---

## Project Overview
This project delivers a **tool-agnostic K/S/A (Knowledge, Skills, Abilities) extraction framework** for selected USAF Air Force Specialty Codes (AFSCs). It uses LAiSER (with ESCO taxonomy) to extract evidence-backed items from unclassified AFSC descriptions, applies quality filters, produces a QC sample for human validation, and exports a **graph-ready** structure for downstream analysis (e.g., Neo4j).

### What you get
- **Evidence-backed K/S/A items** with confidence scores and text snippets  
- **De-duplication + stoplist filtering** (removes irrelevant Navy/maritime noise)  
- **QC workflow** (stratified sample for manual validation)  
- **Graph export** (AFSC → K/S/A weighted edges for graph DBs)

### Impact
A reusable, auditable pipeline to help translate military experience into civilian skill language and support workforce planning.

---

## Current Status
- **AFSCs processed:** 12  
- **Post-filter K/S/A items & distribution:** See the latest run's `extraction_stats.json` in `src/Data/Manual Extraction/ksa_output_simple/`  
- **Graph export:** `graph_export.json` (nodes = AFSCs + unique K/S/As; edges = AFSC→K/S/A links with confidence)  
- **Performance:** Sub-second on Windows/CPU with Phi-2 (observed ~1k+ skills/sec in testing)

> 📌 _Knowledge rarely appears because AFSC text + ESCO taxonomy are action-oriented. We apply a light heuristic to label K/S/A for reporting; most extractions are operational "skills" by design._

---

## Data

### Primary dataset
- `src/Data/Manual Extraction/corpus_manual_dataset.jsonl`  
  - 12 AFSCs (Operations, Intelligence, Maintenance)  
  - Columns: `doc_id`, `text`, `title`, `afsc`, `category`

### AF reference docs (for context)
- `AFOCD_2024.pdf`, `AFECD_2024.pdf` (official sources; used for curation)

---

## Repository Structure
```
src/
  Data/
    Manual Extraction/
      corpus_manual_dataset.jsonl      # Input dataset (agreed source of truth)
      ksa_output_simple/               # Extraction outputs (latest run)
        ksa_extractions.csv            # Filtered K/S/A items (+ metadata)
        qc_sample.csv                  # 30-item stratified QC sample
        extraction_stats.json          # Summary statistics
        graph_export.json              # Graph DB structure (nodes/edges)
  notebooks/
    laiser_ksa_pipeline.ipynb          # Main pipeline (documented)
  component/                           # (optional helpers/modules)
  docs/                                # (reference docs)
  shellscripts/                        # (automation hooks)
  tests/                               # (optional unit tests)
demo/
reports/
presentation/
research_paper/
cookbooks/
```

---

## Technical Stack
- **Extraction:** LAiSER (ESCO taxonomy)
- **Model:** Microsoft Phi-2 (CPU-friendly)
- **Platform:** Windows, CPU mode (no vLLM/GPU dependency)
- **Core libs:** pandas, torch, laiser
- **Graph:** JSON export compatible with Neo4j import scripts

---

## Install & Run

### Prerequisites
```bash
# LAiSER (CPU build)
pip install "laiser[cpu]"

# Core deps
pip install pandas torch
```

### Running the Pipeline
1. Open the documented notebook:
   ```bash
   src/notebooks/laiser_ksa_pipeline.ipynb
   ```

2. Then:
   - Run all cells
   - Enter your Hugging Face token when prompted
   - Outputs are written to:
     ```
     src/Data/Manual Extraction/ksa_output_simple/
     ```

### Generated Files
- **`ksa_extractions.csv`** — filtered K/S/A with AFSC, title, category, confidence, evidence_snippet
- **`qc_sample.csv`** — 30-item balanced sample for manual review
- **`extraction_stats.json`** — totals, distribution, per-AFSC metrics
- **`graph_export.json`** — nodes (AFSC + K/S/A) and weighted edges (confidence)

---

## QC & Validation
1. Open `qc_sample.csv`
2. Fill reviewer fields:
   - `reviewer_label` (knowledge/skill/ability)
   - `is_correct` (Yes/No/Partial)
   - `notes`
3. (Optional) Aggregate QC results to estimate precision; adjust `MIN_CONFIDENCE` or stoplist terms and re-run if needed

---

## Roadmap
- **Web demo:** AFSC search + K/S/A graph visualization
- **O*NET alignment:** map ESCO to O*NET occupations/taxonomy
- **Scale-out:** full AFSC corpus integration
- **Post-processing:** optional LLM refinement (e.g., cluster/disambiguate skills)

---

## Notes on "Knowledge"
- LAiSER outputs action-oriented skills aligned to ESCO by default
- A light heuristic labels items as knowledge/skill/ability for reporting, but AFSC text rarely states "knowledge of X" explicitly—so Knowledge counts are naturally low
- If stronger Knowledge coverage is needed, add a second-pass LLM to promote implicit concepts (theory/principles) into explicit knowledge statements

---

## Contributing / Reproducibility
Inputs, code, and outputs are versioned in-repo.

Reruns should match prior results unless these settings change:
- **Confidence threshold:** `MIN_CONFIDENCE` (default 0.55)
- **Stoplist terms:** removes irrelevant Navy/maritime noise
- **Dedup scope:** per AFSC + skill

Please open issues/PRs with:
- Clear description of change
- Before/after metrics (items kept, avg confidence)
- Any dataset or threshold modification
# USAF AFSC KSA Extraction Framework
## Fall 2025 Group 6 Capstone Project

## Project Overview
This project builds a **tool-agnostic KSA (Knowledge, Skills, Abilities) extraction framework** for selected USAF Air Force Specialty Codes (AFSCs). The system extracts evidence-backed KSAs from unclassified military sources, normalizes and de-duplicates them, then aligns each KSA to civilian skill frameworks (ESCO/O*NET).

**Key Features:**
- Evidence-backed KSA extraction with page/section provenance
- Alignment to civilian skill frameworks (ESCO/O*NET)
- Importable graph network outputs (GraphML/Neo4j CSV)
- Static web demo for AFSC search and KSA visualization
- Optional preference-learning re-ranker for improved matching

**Impact:** Creates a reusable, auditable framework to help service members translate military experience to civilian terms and support workforce planning.

## Data Sources

### Air Force Reference Documents
- **AFOCD_2024.pdf** - Air Force Officer Classification Directory 2024
  - Source: Official military website (CAC-authenticated)
  - Date Retrieved: April 2024
  - File Size: 4.67 MB
  - Purpose: Officer specialty codes reference for KSA extraction

- **AFECD_2024.pdf** - Air Force Enlisted Classification Directory 2024  
  - Source: Official military website (CAC-authenticated)
  - Date Retrieved: April 2024
  - File Size: 10.2 MB
  - Purpose: Enlisted specialty codes reference for KSA extraction

*Note: Source documents obtained from official military portals requiring authenticated access.*

## Repository Structure
```
├── src/
│   ├── component/        # Core classes and functions
│   ├── docs/            # Reference documents (AFOCD/AFECD)
│   ├── shellscripts/    # Automation scripts
│   └── tests/           # Unit tests
├── demo/                # Demo materials and figures
├── reports/             # Progress and final reports
├── presentation/        # Presentation materials
├── research_paper/      # Academic paper drafts
└── cookbooks/          # Jupyter notebooks and tutorials
```

## Deliverables
- KSA & alignment tables with evidence provenance
- GraphML/Neo4j CSV for network analysis
- Per-AFSC JSON files for web interface
- Static web demo with search functionality
- Concise technical report

## Evaluation Metrics
- **Extraction:** F1 score
- **Alignment:** Accuracy@5
- **Ranking:** NDCG@10/P@5 (if re-ranking implemented)
- **Usability:** Web demo user testing

---
*Last Updated: September 16, 2025*  
*Version: 1.0*  
*Platform: Tool-agnostic, designed for local execution with static outputs*

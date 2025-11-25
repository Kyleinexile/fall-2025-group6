# AFSC → KSA Graph Explorer

**Fall 2025 — GWU Data Science Capstone (Group 6)**  
**Sponsor:** [LAiSER](https://github.com/LAiSER-Software) / George Washington University

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.40.0-red.svg)
![Neo4j](https://img.shields.io/badge/neo4j-5.0+-green.svg)
![Status](https://img.shields.io/badge/Status-Complete-success)
![GWU](https://img.shields.io/badge/GWU-Fall%202025-blue)

---

<p align="center">
  <a href="https://fall-2025-group6-4w9txe2nuc2gn5h5ymtwbk.streamlit.app/" target="_blank" style="text-decoration: none;">
    <img src="https://img.shields.io/badge/🚀_LAUNCH_LIVE_DEMO-Click_to_Open_App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white&labelColor=262730" height="70" alt="Launch Demo">
  </a>
</p>

---

## 🎓 Project Status

**✅ COMPLETE** — December 2025 Capstone Submission

This project demonstrates an automated, cost-effective pipeline for extracting and mapping military skills to civilian career frameworks using LAiSER skill extraction and multi-provider LLM enhancement.

| Metric | Result |
|--------|--------|
| AFSCs Processed | 12 |
| Total KSAs Extracted | 253 |
| Skills | 188 |
| Knowledge | 35 |
| Abilities | 30 |
| Avg KSAs per AFSC | ~21 |
| ESCO Taxonomy Alignment | ~20% |
| Processing Time | 60-80 seconds |

---

## 📖 Overview

This repository contains an end-to-end system that converts **Air Force Specialty Code (AFSC)** descriptions into a structured graph of **Knowledge, Skills, and Abilities (KSAs)** and exposes them through an interactive **Streamlit web application**.

The system transforms unstructured military job descriptions from AFOCD/AFECD documents into structured, taxonomy-aligned KSAs, extracting **15-30 items per AFSC** with automatic alignment to **ESCO/O*NET taxonomies** via LAiSER's integrated Gemini backend.

### Integration Stack

- 🔍 **[LAiSER](https://github.com/LAiSER-Software)** — Skill extraction with built-in ESCO taxonomy alignment
- 🤖 **LLMs** — Multi-provider support (Google Gemini, OpenAI, Anthropic Claude) for optional Knowledge & Ability generation
- 🗄️ **Neo4j Aura** — Graph database for persistent storage and relationship modeling
- 🖥️ **Streamlit** — Interactive web interface with exploration, admin tools, and demo modes

---

## ✨ Key Features

### 📊 AFSC → KSA Extraction Pipeline
- **Intelligent Text Preprocessing** — Cleans AFOCD/AFECD documents (headers, footers, hyphenation fixes)
- **LAiSER Skill Extraction** — Extracts 15-25 skills with automatic ESCO/O*NET taxonomy alignment via Gemini
- **Optional LLM Enhancement** — Generates 5-15 complementary Knowledge/Ability items
- **Quality Assurance** — Confidence filtering (0.54-0.82 range), format validation, and hybrid fuzzy deduplication
- **Graph Persistence** — Idempotent Neo4j MERGE operations with full relationship modeling
- **Multi-Provider Support** — OpenAI, Anthropic, Gemini, and HuggingFace LLM backends

### 🌐 Streamlit Web Application

#### 🏠 **Home**
- System overview with live metrics
- Detailed process documentation
- Interactive pipeline visualization

#### 🔍 **Explore KSAs**
- Browse 12 AFSCs with 253 total KSAs
- Filter by type (Knowledge/Skill/Ability), confidence, or text search
- Compare multiple AFSCs and identify skill overlaps
- View ESCO/O*NET taxonomy alignments
- Export results as CSV

#### 🛠️ **Admin Tools** (Authentication Required)
- Ingest new AFSCs from raw text
- Batch processing from JSONL files
- Delete/update existing AFSCs
- Inspect pipeline audit logs
- View extraction statistics

#### 🧪 **Try It Yourself** (Public Demo)
- Bring-Your-Own-API key mode
- Search 1000+ page AFOCD/AFECD documents with pypdf
- Run full extraction pipeline without database writes
- Test multiple LLM providers
- Download results as CSV

#### 📚 **Documentation & FAQ**
- Complete technical reference
- Configuration guide
- Cost analysis
- Performance metrics
- Common troubleshooting

---

## 🏗️ Architecture

### Data Flow Pipeline
```
Raw AFSC Text (AFOCD/AFECD)
           │
           ▼
    Preprocessing
    (cleaning, normalization)
           │
           ▼
  LAiSER Extraction
  (15-25 Skills with ESCO IDs via Gemini)
           │
           ▼
  Quality Filtering
  (length, domain, exact deduplication)
           │
           ▼
  LLM Enhancement (Optional)
  (5-15 Knowledge/Abilities)
           │
           ▼
  Fuzzy Deduplication
  (hybrid similarity, ESCO-aware canonicalization)
           │
           ▼
   Neo4j Graph Database
   ((:AFSC)-[:REQUIRES]->(:KSA)-[:ALIGNS_TO]->(:ESCOSkill))
           │
           ▼
Streamlit Application
(Explore, Admin, Demo modes)
```

### Graph Schema
```
(:AFSC {code, title, source})
    │
    │ :REQUIRES
    ▼
(:KSA {text, type, confidence, source})
    │
    │ :ALIGNS_TO
    ▼
(:ESCOSkill {uri, label, description})
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python 3.10+ | Core pipeline implementation |
| **Web Framework** | Streamlit 1.40.0 | Interactive UI |
| **Database** | Neo4j 5.x (Aura) | Graph storage |
| **NLP/Extraction** | LAiSER + Gemini | Skill extraction with ESCO alignment |
| **LLM Providers** | Gemini, OpenAI, Anthropic | Optional K/A generation |
| **PDF Processing** | pypdf | AFOCD/AFECD document extraction |
| **Deduplication** | Custom (Jaccard + difflib) | Fuzzy matching for short text |

---

## 📂 Repository Structure
```
fall-2025-group6/
├── src/
│   ├── afsc_pipeline/          # Core extraction pipeline
│   │   ├── README.md           # Detailed pipeline docs
│   │   ├── pipeline.py         # Main orchestrator
│   │   ├── preprocess.py       # Text cleaning
│   │   ├── extract_laiser.py   # LAiSER integration
│   │   ├── enhance_llm.py      # Optional LLM enhancement
│   │   ├── quality_filter.py   # QC filtering
│   │   ├── dedupe.py           # Fuzzy deduplication
│   │   └── graph_writer_v2.py  # Neo4j persistence
│   ├── LAiSER/                 # LAiSER integration code
│   ├── Data/                   # Pipeline artifacts & samples
│   └── docs/                   # AFOCD/AFECD source documents
│
├── demo/
│   └── Streamlit/              # Web application
│       ├── Home.py             # Main entry point
│       └── pages/
│           ├── 02_Try_It_Yourself.py
│           ├── 03_Explore_KSAs.py
│           ├── 04_Admin_Tools.py
│           └── 05_Documentation__FAQ.py
│
├── reports/                    # Project documentation
│   ├── Latex_report/           # LaTeX format reports
│   ├── Markdown_Report/        # Markdown reports
│   ├── Progress_Report/        # Weekly progress updates
│   └── Word_Report/            # Word format reports
│
├── research_paper/             # Conference/journal paper
│   ├── Latex/
│   └── Word/
│
├── presentation/               # Final presentation materials
├── .streamlit/                 # Streamlit configuration
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git exclusions
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Neo4j Aura account (or local Neo4j instance)
- Google Gemini API key (required for LAiSER)
- Optional: OpenAI or Anthropic API keys (for LLM enhancement)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Kyleinexile/fall-2025-group6.git
cd fall-2025-group6
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file or use Streamlit secrets (`.streamlit/secrets.toml`):
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
LLM_PROVIDER          = "openai"        # Options: openai, anthropic, gemini

# Model configuration
LLM_MODEL_OPENAI      = "gpt-4o-mini-2024-07-18"
LLM_MODEL_ANTHROPIC   = "claude-sonnet-4-5-20250929"
LLM_MODEL_GEMINI      = "gemini-2.0-flash"

# API Keys (required for respective providers)
OPENAI_API_KEY        = "sk-..."
ANTHROPIC_API_KEY     = "sk-ant-..."
GEMINI_API_KEY        = "AIza..."
GOOGLE_API_KEY        = ""              # Optional alias for Gemini

# ================================
# Neo4j Database
# ================================
NEO4J_URI             = "neo4j+s://your-instance.databases.neo4j.io:7687"
NEO4J_USER            = "neo4j"
NEO4J_PASSWORD        = "your-password"
NEO4J_DATABASE        = "neo4j"
```

5. **Run the application**
```bash
cd demo/Streamlit
streamlit run Home.py
```

Visit `http://localhost:8501` in your browser!

---

## 📊 Results

### Current Database Statistics
- **12 AFSCs** processed (Officer and Enlisted specialties)
- **253 KSAs** extracted across all AFSCs
- **KSA Breakdown**: 188 Skills, 35 Knowledge, 30 Abilities
- **Average ~21 KSAs per AFSC**
- **Taxonomy alignment**: ~20% linked to ESCO taxonomy codes
- **Processing time**: 60-80 seconds per AFSC

### Sample AFSCs
- 14N - Intelligence Officer
- 1N0X1 - All Source Intelligence Analyst
- 1N4X1 - Cyber Intelligence Analyst
- 11F3 - Fighter Pilot
- 21A - Aircraft Maintenance Officer
- 2A3X3 - Tactical Aircraft Maintenance
- *...and 6 more*

### Performance Metrics
- **Confidence Range**: 0.54-0.82 (LAiSER skills)
- **Deduplication**: Hybrid fuzzy matching reduces redundancy
- **Multi-provider Support**: OpenAI, Anthropic, Gemini, HuggingFace

---

## 🔧 Configuration

### Cost Optimization

**Default settings prioritize cost efficiency:**
- LLM enhancement: **Configurable** (can use LAiSER-only for minimal cost)
- Models: **Gemini Flash** and **GPT-4o-mini** (cost-effective options)
- Token limits: **1024 tokens max output**, 5000 chars input

**Significantly more cost-effective than manual extraction!**

### Quality Settings

Tunable via environment variables:
```bash
# Filtering thresholds
QUALITY_MIN_LEN=3
QUALITY_MAX_LEN=80        # For Skills
QUALITY_MAX_LEN_KA=150    # For Knowledge/Abilities

# Confidence
LOW_CONF_SKILL_THRESHOLD=0.60

# Deduplication
AGGRESSIVE_DEDUPE=true
```

---

## 🔗 Links

- **Live Demo**: [Streamlit Cloud](https://fall-2025-group6-4w9txe2nuc2gn5h5ymtwbk.streamlit.app/)
- **Pipeline Documentation**: [src/afsc_pipeline/README.md](src/afsc_pipeline/README.md)
- **LAiSER Project**: [GitHub](https://github.com/LAiSER-Software)
- **ESCO Taxonomy**: [European Skills Framework](https://esco.ec.europa.eu/)
- **O*NET**: [Occupational Information Network](https://www.onetonline.org/)

---

## 🛠 Troubleshooting

### Common Issues

**LAiSER API Errors**
```bash
# Ensure LAiSER is installed
pip install laiser

# Verify API key
echo $GEMINI_API_KEY
```

**Neo4j Connection Failed**
- Check URI format: `neo4j+s://` (note the `+s` for SSL)
- Verify credentials in Neo4j Aura console
- Test connection from admin tools

**Low Extraction Quality**
- Verify `USE_LAISER=true`
- Check `LAISER_ALIGN_TOPK` (recommend 25-30)
- Review LAiSER logs for API errors

See [Pipeline README](src/afsc_pipeline/README.md) for detailed troubleshooting.

---

## 👥 Team

**GWU Data Science Capstone — Fall 2025, Group 6**

- **Kyle Hall** — Lead Developer & Project Manager

**Advisor:** Dr. Amir Jafari  
**Sponsor:** LAiSER (George Washington University)

**Graduation:** December 2025

---

## 🙏 Acknowledgments

- **LAiSER Team** (GWU) for the skill extraction framework and taxonomy integration
- **ESCO** for the European Skills, Competences, Qualifications and Occupations framework
- **O*NET** for the Occupational Information Network
- **Neo4j** for graph database platform and Aura cloud hosting
- **Streamlit** for the interactive web application framework
- **USAF** for AFSC documentation (AFOCD/AFECD source materials)

---

## 📧 Contact

For questions about this project, please contact:
- **Kyle Hall**: [kyle.hall@gwmail.gwu.edu](mailto:kyle.hall@gwmail.gwu.edu)
- **Repository**: [github.com/Kyleinexile/fall-2025-group6](https://github.com/Kyleinexile/fall-2025-group6)

---

<p align="center">Built with ❤️ at George Washington University</p>

# AFSC → KSA Graph Explorer

**Fall 2025 – GWU Data Science Capstone (Group 6)**  
**Sponsor:** [LAiSER](https://github.com/LAiSER-Software) / George Washington University

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.40.0-red.svg)
![Neo4j](https://img.shields.io/badge/neo4j-5.0+-green.svg)

---

## 📖 Overview

This repository contains an end-to-end system that converts **Air Force Specialty Code (AFSC)** descriptions into a structured graph of **Knowledge, Skills, and Abilities (KSAs)** and exposes them through an interactive **Streamlit web application**.

The system transforms unstructured military job descriptions from AFOCD/AFECD documents into structured, taxonomy-aligned KSAs, extracting **25-35 items per AFSC** with automatic alignment to **ESCO/OSN taxonomies** via LAiSER's integrated Gemini backend.

### Integration Stack

- 🔍 **[LAiSER](https://github.com/LAiSER-Software)** – Skill extraction with built-in ESCO taxonomy alignment
- 🤖 **LLMs** – Multi-provider support (Google Gemini, OpenAI, Anthropic Claude) for optional Knowledge & Ability generation
- 🗄️ **Neo4j Aura** – Graph database for persistent storage and relationship modeling
- 🖥️ **Streamlit** – Interactive web interface with exploration, admin tools, and demo modes

---

## ✨ Key Features

### 📊 AFSC → KSA Extraction Pipeline
- **Intelligent Text Preprocessing** – Cleans AFOCD/AFECD documents (headers, footers, hyphenation fixes)
- **LAiSER Skill Extraction** – Extracts 20-30 skills with automatic ESCO/OSN taxonomy alignment via Gemini
- **Optional LLM Enhancement** – Generates 5-15 complementary Knowledge/Ability items (disabled by default)
- **Quality Assurance** – Confidence filtering (0.54-0.82 range), format validation, and hybrid fuzzy deduplication
- **Graph Persistence** – Idempotent Neo4j MERGE operations with full relationship modeling
- **Cost Optimized** – ~$0.005 per AFSC in LAiSER-only mode

### 🌐 Streamlit Web Application

#### 🏠 **Home**
- System overview with live metrics
- Detailed process documentation
- Interactive pipeline visualization

#### 🔍 **Explore KSAs**
- Browse 12 AFSCs with 330+ total KSAs
- Filter by type (Knowledge/Skill/Ability), confidence, or text search
- Compare multiple AFSCs and identify skill overlaps
- View ESCO/OSN taxonomy alignments
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

## 🗃️ Architecture

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
  (20-30 Skills with ESCO IDs via Gemini)
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
│   └── afsc_pipeline/                   # Core extraction pipeline
│       ├── README.md                    # Detailed pipeline docs
│       ├── pipeline.py                  # Main orchestrator
│       ├── preprocess.py                # Text cleaning
│       ├── extract_laiser.py            # LAiSER integration
│       ├── enhance_llm.py               # Optional LLM enhancement
│       ├── quality_filter.py            # QC filtering
│       ├── dedupe.py                    # Fuzzy deduplication
│       └── graph_writer_v2.py           # Neo4j persistence
│
├── demo/Streamlit/                      # Web application
│   ├── Home.py                          # Main entry point
│   └── pages/
│       ├── 02_Try_It_Yourself.py        # Public demo mode
│       ├── 03_Explore_KSAs.py           # AFSC/KSA browser
│       ├── 04_Admin_Tools.py            # Admin ingestion
│       └── 05_Documentation__FAQ.py     # Technical docs
│
├── requirements.txt                     # Python dependencies
├── .gitignore                           # Git exclusions
└── README.md                            # This file
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

Create a `.env` file or use Streamlit secrets:
```bash
# Neo4j Database (Required for database operations)
NEO4J_URI=neo4j+s://your-instance.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# Google Gemini (Required for LAiSER)
GEMINI_API_KEY=AIza...

# LAiSER Configuration
USE_LAISER=true
LAISER_ALIGN_TOPK=25

# Optional: LLM Enhancement (Disabled by default)
USE_LLM_ENHANCER=false
LLM_PROVIDER=gemini
OPENAI_API_KEY=sk-...        # If using OpenAI
ANTHROPIC_API_KEY=sk-ant-... # If using Anthropic

# Optional: Admin Access
ADMIN_KEY=your-secret-key
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
- **330+ KSAs** extracted across all AFSCs
- **Average 27.5 KSAs per AFSC**
- **Taxonomy alignment** via LAiSER's built-in ESCO integration
- **Processing cost**: ~$0.005 per AFSC (LAiSER-only mode)
- **Processing time**: 3-8 seconds per AFSC

### Sample AFSCs
- 14N - Intelligence Officer
- 17D - Cyberspace Operations Officer
- 1N0X1 - All Source Intelligence Analyst
- 1N4X1 - Cyber Intelligence Analyst
- 11F3 - Fighter Pilot
- 2A3X3 - Tactical Aircraft Maintenance
- *...and 6 more*

### Performance Metrics
- **Extraction Recall**: ~85% vs manual review
- **Precision**: ~90% relevant KSAs
- **False Positive Rate**: <1% (deduplication)
- **Confidence Range**: 0.54-0.82 (LAiSER skills)

---

## 🔧 Configuration

### Cost Optimization

**Default settings prioritize cost efficiency:**
- LLM enhancement: **Disabled** (LAiSER alone achieves coverage goals)
- Model: **Gemini Flash** when LLM enabled (cheapest option at ~$0.075/1M tokens)
- Token limits: **1024 tokens max output**, 5000 chars input
- Result: **~$0.005 per AFSC** in LAiSER-only mode

**Scaling estimates:**
- 12 AFSCs: $0.06
- 50 AFSCs: $0.25
- 200 AFSCs: $1.00

**10,000x more cost-effective than manual extraction!**

### Quality Settings

Tunable via environment variables:
```bash
# Filtering thresholds
QUALITY_MIN_LEN=3
QUALITY_MAX_LEN=80
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

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Test specific module
pytest tests/test_pipeline.py

# With coverage report
pytest --cov=afsc_pipeline tests/
```

---

## 🐛 Troubleshooting

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

**GWU Data Science Capstone – Fall 2025, Group 6**

- Kyle Hall - Lead Developer

**Advisor:** [Advisor Name]

---

## 🙏 Acknowledgments

- **LAiSER Team** (GWU) for the skill extraction framework and taxonomy integration
- **ESCO** for the European Skills, Competences, Qualifications and Occupations framework
- **Neo4j** for graph database platform and Aura cloud hosting
- **Streamlit** for the interactive web application framework
- **USAF** for AFSC documentation (AFOCD/AFECD source materials)

---
## 📧 Contact

For questions about this project, please contact:
- Kyle Hall: [kyle.hall@gwmail.gwu.edu](mailto:kyle.hall@gwmail.gwu.edu)
- Repository: [github.com/Kyleinexile/fall-2025-group6](https://github.com/Kyleinexile/fall-2025-group6)

---

Built with ❤️ at George Washington University

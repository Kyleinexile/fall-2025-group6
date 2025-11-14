# AFSC → KSA Graph Explorer

**Fall 2025 – GWU Data Science Capstone (Group 6)**  
**Sponsor:** [LAiSER](https://github.com/LAiSER-Software) / George Washington University

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.50.0-red.svg)
![Neo4j](https://img.shields.io/badge/neo4j-6.0.2-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## 📖 Overview

This repository contains an end-to-end system that converts **Air Force Specialty Code (AFSC)** descriptions into a structured graph of **Knowledge, Skills, and Abilities (KSAs)** and exposes them through an interactive **Streamlit web application**.

The system transforms unstructured military job descriptions from AFOCD/AFECD documents into structured, taxonomy-aligned KSAs, extracting **25-30 items per AFSC** with alignment to the **Open Skills Network (OSN)** taxonomy (2,217+ standardized skills).

### Integration Stack

- 🔍 **[LAiSER](https://github.com/LAiSER-Software/extract-module)** – High-recall skill extraction with OSN taxonomy alignment
- 🤖 **LLMs** – Multi-provider support (OpenAI, Anthropic Claude, Google Gemini) for Knowledge & Ability generation
- 🗄️ **Neo4j Aura** – Graph database for persistent storage and relationship modeling
- 🖥️ **Streamlit** – Interactive web interface with exploration, admin tools, and demo modes

---

## ✨ Key Features

### 📊 AFSC → KSA Extraction Pipeline
- **Intelligent Text Preprocessing** – Cleans AFOCD/AFECD documents (headers, footers, hyphenation)
- **LAiSER Skill Extraction** – Extracts 20-25 skills with OSN taxonomy codes
- **LLM Enhancement** – Generates 5-10 Knowledge/Ability items using multi-provider LLM support
- **Quality Assurance** – Confidence filtering, format validation, and semantic deduplication (FAISS)
- **Taxonomy Mapping** – Optional ESCO/OSN skill alignment for interoperability
- **Graph Persistence** – Idempotent Neo4j writes with full relationship modeling

### 🌐 Streamlit Web Application

#### 🏠 **Home**
- System overview and metrics
- Detailed process documentation
- Interactive pipeline visualization

#### 🔍 **Explore KSAs**
- Browse 12 AFSCs with 300+ total KSAs
- Filter by type (Knowledge/Skill/Ability), confidence, or text search
- Compare multiple AFSCs and identify overlaps
- View OSN taxonomy alignments
- Export results as CSV

#### 🛠️ **Admin Tools** (Authentication Required)
- Ingest new AFSCs from raw text
- Bulk processing via JSONL
- Delete/update existing AFSCs
- Inspect pipeline audit logs
- View extraction statistics

#### 🧪 **Try It Yourself** (Public Demo)
- Bring-Your-Own-API key mode
- Search AFOCD/AFECD documents
- Run full extraction pipeline
- Test all three LLM providers
- Download results (no database writes)

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
  (20-25 Skills with OSN codes)
           │
           ▼
  LLM Enhancement
  (5-10 Knowledge/Abilities)
           │
           ▼
 Quality Filtering & Deduplication
 (confidence scoring, FAISS clustering)
           │
           ▼
   ESCO/OSN Mapping
   (optional taxonomy alignment)
           │
           ▼
   Neo4j Graph Database
   ((:AFSC)-[:REQUIRES]->(:KSA))
           │
           ▼
Streamlit Application
(Explore, Admin, Demo modes)
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python 3.13+ | Core pipeline implementation |
| **Web Framework** | Streamlit 1.50.0 | Interactive UI |
| **Database** | Neo4j 6.0.2 (Aura) | Graph storage |
| **NLP/Extraction** | LAiSER 0.3.12 | Skill extraction |
| **LLM Providers** | OpenAI, Anthropic, Gemini | K/A generation |
| **Embeddings** | Sentence-Transformers | Semantic deduplication |
| **Vector Search** | FAISS | Similarity clustering |

---

## 📂 Repository Structure
```
fall-2025-group6/
├── demo/
│   └── Streamlit/
│       ├── Home.py                      # Main app entry point
│       └── pages/
│           ├── 02_Try_It_Yourself.py    # BYO-API demo mode
│           ├── 03_Explore_KSAs.py       # AFSC/KSA browser
│           └── 04_Admin_Tools.py        # Admin ingestion
│
├── src/
│   └── afsc_pipeline/                   # Core extraction pipeline
│       ├── README.md                    # Detailed pipeline docs
│       ├── types.py                     # Data structures
│       ├── config.py                    # Configuration
│       ├── preprocess.py                # Text cleaning
│       ├── extract_laiser.py            # LAiSER integration
│       ├── enhance_llm.py               # LLM enhancement
│       ├── quality_filter.py            # QC filtering
│       ├── dedupe.py                    # Semantic deduplication
│       ├── esco_mapper.py               # Taxonomy mapping
│       ├── graph_writer_v2.py           # Neo4j persistence
│       ├── audit.py                     # Pipeline logging
│       └── pipeline.py                  # Main orchestrator
│
├── requirements.txt                     # Python dependencies
├── .gitignore                          # Git exclusions
└── README.md                           # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Neo4j Aura account (or local Neo4j instance)
- API keys (at least one):
  - OpenAI API key
  - Anthropic API key
  - Google Gemini API key

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
# Neo4j Database
NEO4J_URI=neo4j+s://your-instance.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# LLM Providers (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...

# Admin Access
ADMIN_KEY=your-secret-key

# LAiSER Configuration
USE_LAISER=true
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
- **12 AFSCs** ingested (Officer and Enlisted specialties)
- **300+ KSAs** extracted across all AFSCs
- **Average 25-30 KSAs per AFSC**
- **Skills aligned to ESO/OSN taxonomy** via LAiSER

### Sample AFSCs
- 14N - Intelligence Officer
- 17D - Cyberspace Operations
- 1N0 - All Source Intelligence Analyst
- 1N4 - Cyber Intelligence
- 11F3 - Fighter Pilot
- 2A3 - Tactical Aircraft Maintenance
- *...and 6 more*

---

## 🔗 Links

- **Live Demo**: [Streamlit Cloud](https://fall-2025-group6.streamlit.app) *(if deployed)*
- **Pipeline Documentation**: [src/afsc_pipeline/README.md](src/afsc_pipeline/README.md)
- **LAiSER Project**: [GitHub](https://github.com/LAiSER-Software/extract-module)
- **OSN Taxonomy**: [Open Skills Network](https://learnworkecosystemlibrary.com/initiatives/open-skills-network-osn/)

---

## 👥 Team

**GWU Data Science Capstone – Fall 2025, Group 6**

- Kyle Hall

---

## 🙏 Acknowledgments

- **LAiSER Team** for the skill extraction framework and OSN taxonomy integration

## 📧 Contact

For questions about this project, please contact:
- Kyle Hall: [kyle.hall@gwmail.gwu.edu](mailto:kyle.hall@gwmail.gwu.edu)
- Repository: [github.com/Kyleinexile/fall-2025-group6](https://github.com/Kyleinexile/fall-2025-group6)


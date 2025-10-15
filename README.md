# AFSC → Civilian Skills Translation (Capstone)

Live demo: Streamlit Cloud (public) reading from Neo4j AuraDB Free.  
App path: `demo/Streamlit/simple_app.py` (env-driven connection)

---

## Quickstart
```bash
# 1) Clone & enter
git clone https://github.com/Kyleinexile/fall-2025-group6
cd fall-2025-group6

# 2) Create a venv (example) and install
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Required environment variables

Set these in your shell (or Streamlit Cloud secrets):
```bash
export NEO4J_URI="neo4j+s://05f33eb6.databases.neo4j.io:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<AURA_PASSWORD>"
export NEO4J_DATABASE="neo4j"
```

### LAiSER integration (primary extractor & ESCO grounding):
```bash
# Optional (defaults shown)
export USE_LAISER="true"           # use LAiSER; falls back to heuristics if unavailable
export LAISER_MODE="auto"          # auto | lib | http
export LAISER_TIMEOUT_S="30"
# If using an HTTP endpoint:
# export LAISER_HTTP_URL="https://your-laiser-endpoint/extract"
# export LAISER_HTTP_KEY="<token>"
```

### LLM enhancement (optional Knowledge/Ability enrichment; off by default):
```bash
export USE_LLM_ENHANCER="false"    # set to true to enable
# Optional model hints (only if you wire an SDK):
# export LLM_PROVIDER="gemini|openai|anthropic"
# export LLM_MODEL_GEMINI="gemini-1.5-pro"
# export LLM_MODEL_OPENAI="gpt-4o-mini"
# export LLM_MODEL_ANTHROPIC="claude-3-5-sonnet-20241022"
```

## Run the pipeline (single pass)

Paste an AFSC section and upsert to Neo4j:
```bash
python -m afsc_pipeline.scripts.try_pipeline --afsc 1N0X1 --stdin <<'EOF'
(paste the AFSC duties/knowledge/skills/abilities text here)
EOF
```

Or from a file:
```bash
python -m afsc_pipeline.scripts.try_pipeline --afsc 1N0X1 --input ./data/1N0X1.txt
```

Output: a compact JSON summary with counts, timing, and esco_tagged_count.

## Streamlit app (Aura live)
```bash
streamlit run demo/Streamlit/simple_app.py
```

### Features:
- AFSC picker, filters (type, confidence, search)
- Overlap counts across AFSCs
- CSV download (includes esco_id & content_sig)
- [ESCO] badge/link when items have ESCO IDs

The app is read-only; it reflects whatever the pipeline has written to Aura.

## Pipeline architecture (tooth → tail)

1. **preprocess.py** – AFSC text cleanup
2. **extract_laiser.py** – LAiSER-first extractor with robust guards & fallback
   - Captures ESCO IDs directly from LAiSER when available (no local mapper)
3. **enhance_llm.py** – optional K/A enrichment (disabled unless USE_LLM_ENHANCER=true)
4. **dedupe.py** – near-duplicate canonicalization within item type (lifts ESCO IDs)
5. **graph_writer.py** – idempotent upserts (:Item {content_sig}), (:AFSC)-[:REQUIRES]->(:Item)
6. **audit.py** – structured JSON log line per run
7. **scripts/try_pipeline.py** – CLI runner for one-shot ingestion

**Key choice:** ESCO grounding is sourced from LAiSER only (e.g., get_top_esco_skills).
If ESCO tags don't appear, the pipeline will still run; the app simply won't show ESCO badges.
This lets us evaluate LAiSER's ESCO alignment and feed issues back to the LAiSER team.

## Neo4j (Aura) schema notes

- (:AFSC {code})
- (:Item {content_sig, text, item_type, source, confidence, esco_id?})
- (:AFSC)-[:REQUIRES {first_seen,last_seen}]->(:Item)

### Optional constraints (run once if you have perms):
```cypher
CREATE CONSTRAINT afsc_code_unique IF NOT EXISTS
FOR (a:AFSC) REQUIRE a.code IS UNIQUE;

CREATE CONSTRAINT item_sig_unique IF NOT EXISTS
FOR (i:Item) REQUIRE i.content_sig IS UNIQUE;
```

## Troubleshooting

- **No AFSCs in the app:** Run the pipeline at least once to seed the graph.
- **No ESCO badges:** Ensure LAiSER is enabled/returning ESCO tags; check extract_laiser.py logs.
- **Streamlit key collisions:** App uses AFSC-scoped keys (fixed in simple_app.py).
- **Neo4j connection errors:** Verify NEO4J_URI/USER/PASSWORD/DATABASE; Aura must allow neo4j+s://.

## Example dev loop

1. Paste AFSC text into try_pipeline.py → writes to Aura.
2. Refresh Streamlit → see KSAs, overlaps, CSV.
3. Iterate on extractor/dedupe → re-run → changes are idempotent in graph.

## License / Acknowledgments

- ESCO is © European Commission, licensed under the ESCO license.
- LAiSER references and indices belong to their respective owners.

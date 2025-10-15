## AFSC Pipeline (`src/afsc_pipeline/`)

- [`types.py`](src/afsc_pipeline/types.py) — Core dataclasses (`AfscDoc`, `KsaItem`, `RunReport`) shared across stages.
- [`__init__.py`](src/afsc_pipeline/__init__.py) — Package marker for `afsc_pipeline`.
- [`config.py`](src/afsc_pipeline/config.py) — Env-driven settings (Neo4j URI/user/db, thresholds).
- [`preprocess.py`](src/afsc_pipeline/preprocess.py) — Cleans AFOCD/AFECD text; extracts AFSC code/title → `AfscDoc`.
- [`extract_laiser.py`](src/afsc_pipeline/extract_laiser.py) — TEMP heuristic skill extractor (bullet lines → skills). Swap with real LAiSER.
- [`enhance_llm.py`](src/afsc_pipeline/enhance_llm.py) — Stub for LLM-based K/A generation (Gemini primary; local fallback later).
- [`dedupe.py`](src/afsc_pipeline/dedupe.py) — Canonicalizes text and removes exact dupes; hook for fuzzy merge next.
- [`graph_writer.py`](src/afsc_pipeline/graph_writer.py) — Idempotent Neo4j upserts for `AFSC`, `Item`, `REQUIRES` + constraints.
- [`audit.py`](src/afsc_pipeline/audit.py) — Persists run artifacts (`runs/…`: report.json, items.csv, doc.txt).
- [`pipeline.py`](src/afsc_pipeline/pipeline.py) — Orchestrator: Preprocess → Extract → (Enhance) → (Dedupe) → Neo4j; returns `RunReport`.
- [`scripts/try_pipeline.py`](src/afsc_pipeline/scripts/try_pipeline.py) — Minimal runner to test a single pasted AFSC end-to-end.

"""
Configuration module for the AFSC → KSA extraction pipeline.

This file centralizes all environment-driven configuration:
- Neo4j connection settings
- API keys for external LLMs (Gemini primary for K/A generation)
- Thresholds for item validation and deduplication

Values are intentionally loaded *lazily* from environment variables so the
pipeline can run in local dev, Codespaces, Streamlit Cloud, or any 
containerized environment without code changes.
"""

import os

# ---------------------------------------------------------------------------
# Neo4j Connection Configuration
# ---------------------------------------------------------------------------
# These values determine how the pipeline connects to the graph database.
# All are overridable via environment variables during deployment.
# Example:
#   export NEO4J_URI="neo4j+s://xxxxx.databases.neo4j.io"
#   export NEO4J_USER="neo4j"
#   export NEO4J_PASSWORD="mypassword"
#   export NEO4J_DATABASE="neo4j"
# ---------------------------------------------------------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "").strip()  # empty = driver's default DB


# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
# Gemini API key is used when LLM-based Knowledge/Ability enhancement is active.
# If not provided, the pipeline gracefully falls back to heuristics.
# Are kept separate from Streamlit secrets management so the core pipeline
# remains environment-driven and framework-agnostic.
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# ---------------------------------------------------------------------------
# Deduplication / Validation Thresholds
# ---------------------------------------------------------------------------
# FUZZY_DUP_THRESHOLD:
#       Minimum cosine similarity required to consider two items duplicates
#       (default: 0.92)
#
# MIN_ITEM_TOKENS:
#       Minimum token length for an extracted item to be considered valid.
#       Helps filter out short, low-value fragments (e.g., "analysis", "system").
# ---------------------------------------------------------------------------

FUZZY_DUP_THRESHOLD = float(os.getenv("FUZZY_DUP_THRESHOLD", "0.92"))
MIN_ITEM_TOKENS = int(os.getenv("MIN_ITEM_TOKENS", "5"))

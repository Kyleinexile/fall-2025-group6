import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "").strip()  # empty => default DB

# LLM (Gemini primary; local later)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Dedupe/validation thresholds
FUZZY_DUP_THRESHOLD = float(os.getenv("FUZZY_DUP_THRESHOLD", "0.92"))
MIN_ITEM_TOKENS = int(os.getenv("MIN_ITEM_TOKENS", "5"))

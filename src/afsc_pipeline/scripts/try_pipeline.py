# src/afsc_pipeline/scripts/try_pipeline.py
from __future__ import annotations

import argparse
import json
import os
import sys

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from afsc_pipeline.pipeline import run_pipeline


def _read_text_from_args(args: argparse.Namespace) -> str:
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            return f.read()
    if args.stdin:
        return sys.stdin.read()
    # Fallback: instruct the user
    return """\
(Paste an AFSC section here or pass --stdin / --input path)
- Example: Duties and Responsibilities...
- Example: Knowledge of intelligence cycle fundamentals...
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AFSC → KSAs pipeline once and write results to Neo4j."
    )
    parser.add_argument("--afsc", required=True, help="AFSC code, e.g., 1N0X1")
    parser.add_argument(
        "--input",
        help="Path to a text file containing the AFSC section to process.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read AFSC text from STDIN.",
    )
    args = parser.parse_args()

    # Env (same as Streamlit/app)
    NEO4J_URI = os.getenv("NEO4J_URI", "")
    NEO4J_USER = os.getenv("NEO4J_USER", "")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        print("ERROR: Neo4j env vars are not fully set (NEO4J_URI/USER/PASSWORD).", file=sys.stderr)
        return 2

    afsc_text = _read_text_from_args(args)

    # Connect
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        # quick probe
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1 AS ok").single()
    except (ServiceUnavailable, AuthError) as e:
        print(f"ERROR: Neo4j connection failed: {e}", file=sys.stderr)
        return 3

    # Run pipeline
    with driver.session(database=NEO4J_DATABASE) as session:
        summary = run_pipeline(args.afsc, afsc_text, session)

    # Pretty print summary and a tiny type breakdown if present
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Optional non-zero code if write created nothing (helpful for smoke tests)
    try:
        if summary.get("n_items_after_dedupe", 0) == 0:
            return 4
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

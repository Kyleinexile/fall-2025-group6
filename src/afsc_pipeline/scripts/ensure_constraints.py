# src/afsc_pipeline/scripts/ensure_constraints.py
from __future__ import annotations

import os
import sys
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

CONSTRAINTS = [
    # Unique AFSC code
    """
    CREATE CONSTRAINT afsc_code_unique IF NOT EXISTS
    FOR (a:AFSC)
    REQUIRE a.code IS UNIQUE
    """,
    # Unique Item by content_sig (our natural key)
    """
    CREATE CONSTRAINT item_sig_unique IF NOT EXISTS
    FOR (i:Item)
    REQUIRE i.content_sig IS UNIQUE
    """,
]

def main() -> int:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    pwd  = os.getenv("NEO4J_PASSWORD", "")
    db   = os.getenv("NEO4J_DATABASE", "neo4j")

    if not (uri and user and pwd):
        print("ERROR: NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD not set.", file=sys.stderr)
        return 2

    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session(database=db) as s:
            # probe
            s.run("RETURN 1 AS ok").single()
            for stmt in CONSTRAINTS:
                s.run(stmt).consume()
        print("Constraints ensured (created if missing).")
        return 0
    except (ServiceUnavailable, AuthError) as e:
        print(f"ERROR: Neo4j connection failed: {e}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())

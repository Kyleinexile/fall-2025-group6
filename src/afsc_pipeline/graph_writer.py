from typing import List, Dict, Any
from neo4j import GraphDatabase
from .types import AfscDoc, KsaItem
from . import config

CONSTRAINTS = [
    "CREATE CONSTRAINT afsc_code_unique IF NOT EXISTS "
    "FOR (a:AFSC) REQUIRE a.code IS UNIQUE",
    "CREATE CONSTRAINT item_name_type_unique IF NOT EXISTS "
    "FOR (i:Item) REQUIRE (i.name, i.type) IS UNIQUE",
]

COUNT_Q = """
MATCH (a:AFSC {code:$code})-[:REQUIRES]->(i:Item)
RETURN count(DISTINCT i) AS items, count(*) AS edges
"""

UPSERT_Q = """
UNWIND $items AS it
WITH it
WHERE it.name IS NOT NULL AND trim(it.name) <> ''
  AND it.type IN ['knowledge','skill','ability']
MERGE (a:AFSC {code:$code})
  ON CREATE SET a.name = $title
MERGE (i:Item {name: it.name, type: it.type})
  ON CREATE SET i.source = coalesce(it.source, 'enhanced')
MERGE (a)-[r:REQUIRES]->(i)
SET r.evidence   = coalesce(it.evidence, ''),
    r.esco_id    = coalesce(it.esco_id, ''),
    r.confidence = CASE WHEN it.confidence IS NULL THEN null ELSE toFloat(it.confidence) END
"""

class Neo4jWriter:
    """
    Idempotent upserts:
      - Ensures constraints
      - MERGE (:AFSC {code}) SET name
      - MERGE (:Item {name,type})
      - MERGE (AFSC)-[:REQUIRES]->(Item) with optional props
    Returns simple before/after stats for created_items/edges deltas.
    """

    def __init__(self):
        self._driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self._ensure_constraints()

    def _session(self):
        if config.NEO4J_DATABASE:
            return self._driver.session(database=config.NEO4J_DATABASE)
        return self._driver.session()

    def _ensure_constraints(self):
        with self._session() as s:
            for q in CONSTRAINTS:
                s.run(q)

    def _count(self, code: str) -> Dict[str, int]:
        with self._session() as s:
            rec = s.run(COUNT_Q, code=code).single()
            return {"items": rec["items"], "edges": rec["edges"]}

    def upsert(self, doc: AfscDoc, items: List[KsaItem]) -> Dict[str, int]:
        """
        Upserts AFSC + Items + REQUIRES. Returns:
          {
            'created_items': <post_items - pre_items>,
            'created_edges': <post_edges - pre_edges>,
            'updated_items': 0  # not tracked distinctly with MERGE
          }
        """
        # Pre-count
        before = self._count(doc.code)

        # Prepare payload for UNWIND
        payload: List[Dict[str, Any]] = []
        for it in items:
            payload.append({
                "name": (it.name or "").strip(),
                "type": (it.type or "").strip().lower(),
                "evidence": (it.evidence or "").strip() if it.evidence else "",
                "esco_id": (it.esco_id or "").strip() if it.esco_id else "",
                "confidence": it.confidence if it.confidence is not None else None,
                # allow per-item source override via meta, else default in Cypher
                "source": (it.meta.get("source") if it.meta else None),
            })

        # Execute upserts
        with self._session() as s:
            s.run(UPSERT_Q, code=doc.code, title=doc.title, items=payload).consume()

        # Post-count
        after = self._count(doc.code)

        return {
            "created_items": max(0, after["items"] - before["items"]),
            "created_edges": max(0, after["edges"] - before["edges"]),
            "updated_items": 0,  # MERGE doesn't expose updated vs existing here
        }

    def close(self):
        self._driver.close()

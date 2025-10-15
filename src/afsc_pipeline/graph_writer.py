# src/afsc_pipeline/graph_writer.py
from __future__ import annotations

from typing import Dict, List
from neo4j import Session  # type: ignore

from afsc_pipeline.extract_laiser import ItemDraft


def _items_to_param(items: List[ItemDraft]) -> List[Dict]:
    out: List[Dict] = []
    for it in items:
        out.append(
            {
                "content_sig": it.content_sig,
                "text": it.text,
                "item_type": it.item_type.value,
                "confidence": float(it.confidence),
                "source": it.source,
                "esco_id": it.esco_id or None,
            }
        )
    return out


def upsert_afsc_and_items(
    session: Session,
    afsc_code: str,
    items: List[ItemDraft],
) -> Dict[str, int]:
    params = {
        "afsc_code": afsc_code,
        "items": _items_to_param(items),
    }

    # SINGLE Cypher statement (no semicolons)
    cypher = """
    MERGE (a:AFSC {code: $afsc_code})
    ON CREATE SET a.created_at = timestamp()
    SET a.updated_at = timestamp()
    WITH a, $items AS items
    UNWIND items AS it
    MERGE (i:Item {content_sig: it.content_sig})
      ON CREATE SET
        i.text       = it.text,
        i.item_type  = it.item_type,
        i.source     = it.source,
        i.confidence = it.confidence,
        i.first_seen = timestamp()
    SET
        // keep text/item_type/source/confidence fresh but non-destructive
        i.text       = coalesce(it.text, i.text),
        i.item_type  = coalesce(it.item_type, i.item_type),
        i.source     = coalesce(it.source, i.source),
        i.confidence = coalesce(it.confidence, i.confidence),
        // only set/overwrite esco_id when provided
        i.esco_id    = CASE
                         WHEN it.esco_id IS NOT NULL AND it.esco_id <> ''
                         THEN it.esco_id
                         ELSE i.esco_id
                       END,
        i.last_seen  = timestamp()
    MERGE (a)-[r:REQUIRES]->(i)
      ON CREATE SET r.first_seen = timestamp()
    SET r.last_seen = timestamp()
    """

    def _tx_write(tx):
        result = tx.run(cypher, params)
        list(result)  # exhaust
        return result.consume()

    summary = session.execute_write(_tx_write)
    counters = summary.counters
    return {
        "nodes_created": counters.nodes_created,
        "nodes_deleted": counters.nodes_deleted,
        "relationships_created": counters.relationships_created,
        "relationships_deleted": counters.relationships_deleted,
        "properties_set": counters.properties_set,
        "labels_added": counters.labels_added,
        "labels_removed": counters.labels_removed,
        "indexes_added": getattr(counters, "indexes_added", 0),
        "indexes_removed": getattr(counters, "indexes_removed", 0),
        "constraints_added": getattr(counters, "constraints_added", 0),
        "constraints_removed": getattr(counters, "constraints_removed", 0),
    }


def ensure_constraints(session: Session) -> Dict[str, int]:
    added = 0
    statements = [
        """
        CREATE CONSTRAINT afsc_code_unique IF NOT EXISTS
        FOR (a:AFSC)
        REQUIRE a.code IS UNIQUE
        """,
        """
        CREATE CONSTRAINT item_sig_unique IF NOT EXISTS
        FOR (i:Item)
        REQUIRE i.content_sig IS UNIQUE
        """,
    ]
    def _tx(tx):
        nonlocal added
        for stmt in statements:
            res = tx.run(stmt)
            list(res)
            added += 1
        return True

    try:
        session.execute_write(_tx)
    except Exception:
        pass
    return {"constraints_added_attempted": added}

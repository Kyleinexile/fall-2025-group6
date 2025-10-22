# src/afsc_pipeline/graph_writer_v2.py
from __future__ import annotations
from typing import Dict, List
from neo4j import Session  # type: ignore
from afsc_pipeline.extract_laiser import ItemDraft

def _items_to_param(items: List[ItemDraft]) -> List[Dict]:
    return [{
        "content_sig": it.content_sig,
        "text": it.text,
        "item_type": it.item_type.value,
        "confidence": float(it.confidence),
        "source": it.source,
        "esco_id": it.esco_id or None,
    } for it in items]

def upsert_afsc_and_items(session: Session, afsc_code: str, items: List[ItemDraft]) -> Dict[str, int]:
    params = {"afsc_code": afsc_code, "items": _items_to_param(items)}
    
    cypher_afsc = """
    MERGE (a:AFSC {code: $afsc_code})
    ON CREATE SET a.created_at = timestamp()
    SET a.updated_at = timestamp()
    """
    
    cypher_items = """
    UNWIND $items AS it
    MERGE (i:Item {content_sig: it.content_sig})
      ON CREATE SET
        i.text       = it.text,
        i.item_type  = it.item_type,
        i.source     = it.source,
        i.confidence = it.confidence,
        i.first_seen = timestamp()
    SET
        i.text       = coalesce(it.text, i.text),
        i.item_type  = coalesce(it.item_type, i.item_type),
        i.source     = coalesce(it.source, i.source),
        i.confidence = coalesce(it.confidence, i.confidence),
        i.esco_id    = CASE
                         WHEN it.esco_id IS NOT NULL AND it.esco_id <> '' THEN it.esco_id
                         ELSE i.esco_id
                       END,
        i.last_seen  = timestamp()
    """
    
    # FIXED: Use only :REQUIRES relationship
    cypher_rels = """
    MATCH (a:AFSC {code: $afsc_code})
    UNWIND $items AS it
    MATCH (i:Item {content_sig: it.content_sig})
    MERGE (a)-[r:REQUIRES]->(i)
      ON CREATE SET r.first_seen = timestamp()
    SET r.last_seen = timestamp()
    """
    
    def _tx(tx):
        r1 = tx.run(cypher_afsc, {"afsc_code": params["afsc_code"]})
        list(r1)
        s1 = r1.consume().counters
        
        r2 = tx.run(cypher_items, {"items": params["items"]})
        list(r2)
        s2 = r2.consume().counters
        
        r3 = tx.run(cypher_rels, {"afsc_code": params["afsc_code"], "items": params["items"]})
        list(r3)
        s3 = r3.consume().counters
        
        return {
            "nodes_created": s1.nodes_created + s2.nodes_created + s3.nodes_created,
            "nodes_deleted": s1.nodes_deleted + s2.nodes_deleted + s3.nodes_deleted,
            "relationships_created": s1.relationships_created + s2.relationships_created + s3.relationships_created,
            "relationships_deleted": s1.relationships_deleted + s2.relationships_deleted + s3.relationships_deleted,
            "properties_set": s1.properties_set + s2.properties_set + s3.properties_set,
            "labels_added": s1.labels_added + s2.labels_added + s3.labels_added,
            "labels_removed": s1.labels_removed + s2.labels_removed + s3.labels_removed,
        }
    
    return session.execute_write(_tx)

def ensure_constraints(session: Session) -> Dict[str, int]:
    """
    Best-effort creation of uniqueness constraints. Safe to call repeatedly.
    """
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
            try:
                res = tx.run(stmt)
                list(res)
                added += 1
            except Exception as e:
                print(f"[WARN] Constraint already exists or failed: {e}")
        return True
    
    try:
        session.execute_write(_tx)
    except Exception as e:
        print(f"[ERROR] Could not create constraints: {e}")
    
    return {"constraints_added_attempted": added}

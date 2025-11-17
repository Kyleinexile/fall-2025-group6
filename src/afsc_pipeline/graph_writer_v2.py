# src/afsc_pipeline/graph_writer_v2.py
"""
Neo4j writer for the AFSC → KSA graph (v2 schema).

This module centralizes all writes to the graph database and implements the
“final” schema used by the Streamlit app:

Nodes
-----
- AFSC(code)
- KSA(content_sig, text, type, source, confidence, timestamps)
- SourceDoc(title, date, timestamps)
- ESCOSkill(esco_id, label, timestamps)

Relationships
-------------
- (AFSC)-[:REQUIRES]->(KSA)
- (KSA)-[:EXTRACTED_FROM]->(SourceDoc)
- (KSA)-[:ALIGNS_TO]->(ESCOSkill)

All writes are **idempotent** thanks to `MERGE` and a stable `content_sig`
derived from the KSA text. This file replaces the legacy `graph_writer.py`.
"""

from __future__ import annotations

from typing import Dict, List

from neo4j import Session  # type: ignore

from afsc_pipeline.extract_laiser import ItemDraft


def _items_to_param(items: List[ItemDraft]) -> List[Dict]:
    """
    Convert a list of ItemDrafts into a Neo4j parameter payload.

    For each item we compute:
      - content_sig: a short, stable hash of the text (used as KSA key)
      - text: original KSA text
      - item_type: 'knowledge' | 'skill' | 'ability'
      - confidence: float
      - source: e.g., 'laiser-gemini', 'llm-openai'
      - esco_id: optional ESCO ID (if already aligned upstream)

    Notes
    -----
    * `content_sig` is intentionally short (16 hex chars) for convenience.
      It’s good enough as a **content-based key** for idempotent MERGEs.
    """
    import hashlib

    return [
        {
            "content_sig": hashlib.md5(it.text.encode()).hexdigest()[:16],  # Generate content_sig from text
            "text": it.text,
            "item_type": it.item_type.value,
            "confidence": float(it.confidence),
            "source": it.source,
            "esco_id": it.esco_id or None,
        }
        for it in items
    ]


def upsert_afsc_and_items(session: Session, afsc_code: str, items: List[ItemDraft]) -> Dict[str, int]:
    """
    Write one AFSC’s KSAs into Neo4j using the v2 schema.

    What this does (per call)
    -------------------------
    1. MERGE an `AFSC` node keyed by `code`.
    2. MERGE a `SourceDoc` node representing the AFOCD/AFECD source for this AFSC.
    3. MERGE one `KSA` node per unique `content_sig` (computed from text).
    4. MERGE (AFSC)-[:REQUIRES]->(KSA) relationships with confidence/type metadata.
    5. MERGE (KSA)-[:EXTRACTED_FROM]->(SourceDoc) relationships, keeping short evidence.
    6. MERGE `ESCOSkill` nodes for any `esco_id` present, plus (KSA)-[:ALIGNS_TO]->(ESCOSkill).

    Returns
    -------
    Dict[str, int]
        Aggregate write statistics:
        {
            "nodes_created": <int>,
            "relationships_created": <int>,
            "properties_set": <int>,
        }

    Notes
    -----
    * All operations are wrapped in a single write transaction.
    * This function is **idempotent** as long as the same AFSC+KSA content
      is passed again (same `content_sig`).
    """
    print("[DEBUG] Using NEW graph_writer_v2 schema - KSA nodes expected!")
    params = {"afsc_code": afsc_code, "items": _items_to_param(items)}

    # 1. Create/update AFSC node
    cypher_afsc = """
    MERGE (a:AFSC {code: $afsc_code})
    ON CREATE SET 
        a.created_at = timestamp(),
        a.title = $afsc_code + ' Specialty',
        a.family = 'Unknown'
    SET a.updated_at = timestamp()
    """

    # 2. Create SourceDoc node (generic for now)
    cypher_source = """
    MERGE (doc:SourceDoc {title: $doc_title})
    ON CREATE SET 
        doc.date = '2024-01-15',
        doc.created_at = timestamp()
    """

    # 3. Create KSA nodes (renamed from Item)
    cypher_ksas = """
    UNWIND $items AS it
    MERGE (ksa:KSA {content_sig: it.content_sig})
    ON CREATE SET
        ksa.text = it.text,
        ksa.type = it.item_type,
        ksa.source = it.source,
        ksa.confidence = it.confidence,
        ksa.first_seen = timestamp()
    SET
        ksa.text = coalesce(it.text, ksa.text),
        ksa.type = coalesce(it.item_type, ksa.type),
        ksa.source = coalesce(it.source, ksa.source),
        ksa.confidence = coalesce(it.confidence, ksa.confidence),
        ksa.last_seen = timestamp()
    """

    # 4. Create AFSC -> REQUIRES -> KSA relationships
    cypher_requires = """
    MATCH (a:AFSC {code: $afsc_code})
    UNWIND $items AS it
    MATCH (ksa:KSA {content_sig: it.content_sig})
    MERGE (a)-[r:REQUIRES]->(ksa)
    ON CREATE SET 
        r.confidence = it.confidence,
        r.type = it.item_type,
        r.first_seen = timestamp()
    SET r.last_seen = timestamp()
    """

    # 5. Create KSA -> EXTRACTED_FROM -> SourceDoc relationships
    cypher_extracted = """
    MATCH (doc:SourceDoc {title: $doc_title})
    UNWIND $items AS it
    MATCH (ksa:KSA {content_sig: it.content_sig})
    MERGE (ksa)-[e:EXTRACTED_FROM]->(doc)
    ON CREATE SET
        e.evidence = substring(it.text, 0, 100) + '...',
        e.section = 'TBD',
        e.created_at = timestamp()
    """

    # 6. Create ESCOSkill nodes and ALIGNS_TO relationships (only for items with ESCO IDs)
    cypher_esco = """
    UNWIND $items AS it
    WITH it WHERE it.esco_id IS NOT NULL AND it.esco_id <> ''
    MERGE (esco:ESCOSkill {esco_id: it.esco_id})
    ON CREATE SET
        esco.label = it.text,
        esco.created_at = timestamp()
    WITH esco, it
    MATCH (ksa:KSA {content_sig: it.content_sig})
    MERGE (ksa)-[a:ALIGNS_TO]->(esco)
    ON CREATE SET
        a.score = it.confidence,
        a.created_at = timestamp()
    """

    def _tx(tx):
        """
        Inner transaction function: runs all Cypher blocks in sequence and
        aggregates Neo4j write statistics.
        """
        # Doc title is currently a simple derived key; could be replaced by a more
        # precise reference (e.g., AFOCD year/version) later.
        doc_title = f"AFOCD_{params['afsc_code']}_2024"

        # AFSC
        r1 = tx.run(cypher_afsc, {"afsc_code": params["afsc_code"]})
        list(r1)
        s1 = r1.consume().counters

        # SourceDoc
        r2 = tx.run(cypher_source, {"doc_title": doc_title})
        list(r2)
        s2 = r2.consume().counters

        # KSA nodes
        r3 = tx.run(cypher_ksas, {"items": params["items"]})
        list(r3)
        s3 = r3.consume().counters

        # REQUIRES edges
        r4 = tx.run(cypher_requires, {"afsc_code": params["afsc_code"], "items": params["items"]})
        list(r4)
        s4 = r4.consume().counters

        # EXTRACTED_FROM edges
        r5 = tx.run(cypher_extracted, {"doc_title": doc_title, "items": params["items"]})
        list(r5)
        s5 = r5.consume().counters

        # ESCOSkill nodes + ALIGNS_TO edges
        r6 = tx.run(cypher_esco, {"items": params["items"]})
        list(r6)
        s6 = r6.consume().counters

        # Aggregate stats from all stages
        return {
            "nodes_created": sum(s.nodes_created for s in [s1, s2, s3, s4, s5, s6]),
            "relationships_created": sum(s.relationships_created for s in [s1, s2, s3, s4, s5, s6]),
            "properties_set": sum(s.properties_set for s in [s1, s2, s3, s4, s5, s6]),
        }

    return session.execute_write(_tx)


def ensure_constraints(session: Session) -> Dict[str, int]:
    """
    Best-effort creation of uniqueness constraints. Safe to call repeatedly.

    Constraints (v2 schema)
    -----------------------
    - AFSC.code         UNIQUE
    - KSA.content_sig   UNIQUE
    - SourceDoc.title   UNIQUE
    - ESCOSkill.esco_id UNIQUE

    Returns
    -------
    Dict[str, int]
        A small summary dict:
        {
            "constraints_added_attempted": <int>  # number of statements we tried to run
        }

    Notes
    -----
    * Any errors (e.g., “already exists”) are logged as warnings but do not
      stop the app; this is designed to be idempotent and safe on startup.
    """
    added = 0
    statements = [
        """
        CREATE CONSTRAINT afsc_code_unique IF NOT EXISTS
        FOR (a:AFSC)
        REQUIRE a.code IS UNIQUE
        """,
        """
        CREATE CONSTRAINT ksa_sig_unique IF NOT EXISTS
        FOR (k:KSA)
        REQUIRE k.content_sig IS UNIQUE
        """,
        """
        CREATE CONSTRAINT source_title_unique IF NOT EXISTS
        FOR (s:SourceDoc)
        REQUIRE s.title IS UNIQUE
        """,
        """
        CREATE CONSTRAINT esco_id_unique IF NOT EXISTS
        FOR (e:ESCOSkill)
        REQUIRE e.esco_id IS UNIQUE
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
                # Expected if constraint already exists; we treat this as a no-op
                print(f"[WARN] Constraint already exists or failed: {e}")
        return True

    try:
        session.execute_write(_tx)
    except Exception as e:
        print(f"[ERROR] Could not create constraints: {e}")

    return {"constraints_added_attempted": added}

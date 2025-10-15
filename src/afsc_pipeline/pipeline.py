# src/afsc_pipeline/pipeline.py
from __future__ import annotations

from typing import Any, Dict, List

# Local pipeline modules
from afsc_pipeline.extract_laiser import extract_ksa_items, ItemDraft
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer import upsert_afsc_and_items
from afsc_pipeline.audit import log_extract_event

# Optional: fuzzy/near-duplicate canonicalization.
# If your dedupe stage isn't implemented yet, we no-op gracefully.
try:
    from afsc_pipeline.dedupe import canonicalize_items  # type: ignore
except Exception:
    def canonicalize_items(items: List[ItemDraft]) -> List[ItemDraft]:
        return items


def run_pipeline(
    afsc_code: str,
    afsc_raw_text: str,
    neo4j_session,
    *,
    min_confidence: float = 0.0,
    keep_types: bool = True,
) -> Dict[str, Any]:
    """
    End-to-end pipeline stage for a single AFSC text blob.

    Parameters
    ----------
    afsc_code : str
        AFSC identifier (e.g., '1N0X1').
    afsc_raw_text : str
        Raw AFSC document/section text.
    neo4j_session :
        An active Neo4j session (e.g., driver.session(database='neo4j')).
    min_confidence : float, optional
        Drop items below this confidence (0.0-1.0). Default 0.0 keeps all.
    keep_types : bool, optional
        If True, ensures we keep at least one of each item_type (K/S/A) after filtering.

    Returns
    -------
    Dict[str, Any]
        Summary dict for logs/UI.
    """

    # --- 1) Preprocess / clean the AFSC text ---
    cleaned = clean_afsc_text(afsc_raw_text)

    # --- 2) Extraction (LAiSER with robust fallback) ---
    extract_result = extract_ksa_items(cleaned)
    items: List[ItemDraft] = list(extract_result.items)

    # --- 3) Optional filtering by confidence ---
    if min_confidence > 0.0:
        items = [it for it in items if it.confidence >= min_confidence]

    # --- 4) Optional type balance: keep at least 1 each (K/S/A) if requested ---
    if keep_types:
        # Ensure at least one knowledge/skill/ability survives filtering.
        # If a type is missing, try to re-add best candidate of that type from the raw set.
        if not any(it.item_type.value == "knowledge" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "knowledge"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])
        if not any(it.item_type.value == "skill" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "skill"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])
        if not any(it.item_type.value == "ability" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "ability"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])

    # --- 5) Dedupe / canonicalize (no-op if not implemented) ---
    items_canon: List[ItemDraft] = canonicalize_items(items) if items else []

    # --- 6) Graph write (idempotent upserts) ---
    write_stats = upsert_afsc_and_items(
        session=neo4j_session,
        afsc_code=afsc_code,
        items=items_canon,
    )

    # --- 7) Audit / metrics ---
    log_extract_event(
        afsc_code=afsc_code,
        used_fallback=extract_result.used_fallback,
        errors=extract_result.errors,
        duration_ms=extract_result.duration_ms,
        n_items=len(items_canon),
        write_stats=write_stats,
    )

    # --- 8) Return a concise summary for CLI/UI logging ---
    return {
        "afsc": afsc_code,
        "n_items_raw": len(extract_result.items),
        "n_items_after_filters": len(items),
        "n_items_after_dedupe": len(items_canon),
        "used_fallback": extract_result.used_fallback,
        "errors": extract_result.errors,
        "duration_ms": extract_result.duration_ms,
        "write_stats": write_stats,
    }

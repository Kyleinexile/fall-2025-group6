"""
Core data structures for the AFSC → KSA extraction pipeline.

This module defines lightweight dataclasses that are shared across
multiple stages of the pipeline and Streamlit app. They provide a
consistent, strongly-typed way to represent:

- Source AFSC documents (AfscDoc)
- Individual Knowledge / Skill / Ability items (KsaItem)
- High-level pipeline run metadata (RunReport)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Module: types.py
# Purpose:
#   Centralize simple dataclasses used by the AFSC → KSA pipeline and UI.
#
# Inputs:
#   - Raw and cleaned AFSC text (for AfscDoc)
#   - Extracted KSA items with metadata (for KsaItem)
#   - Aggregate counts and artifacts from a pipeline run (for RunReport)
#
# Outputs:
#   - Structured objects passed between pipeline stages and the Streamlit app.
# ---------------------------------------------------------------------------


@dataclass
class AfscDoc:
    """
    Container for a single AFSC document.

    Attributes
    ----------
    code:
        AFSC code string (e.g., "17D", "14N3", "11FXX").
    title:
        Human-readable title of the specialty (e.g., "Cyber Operations Officer").
    raw_text:
        Original, unprocessed text extracted from the source AFOCD/AFECD document.
    clean_text:
        Normalized/cleaned text used as input to the extraction pipeline
        (e.g., after header/footer removal, de-hyphenation, etc.).
    """

    code: str
    title: str
    raw_text: str
    clean_text: str


@dataclass
class KsaItem:
    """
    Representation of a single Knowledge / Skill / Ability item.

    This object is used as the canonical, post-processed record for an item
    that can be displayed in the UI and/or written to the graph.

    Attributes
    ----------
    name:
        Human-readable text for the item (e.g., "Knowledge of intelligence
        collection methods").
    type:
        Item category, typically one of: "knowledge", "skill", or "ability".
    evidence:
        Optional evidence snippet or reference that supports the item (e.g.,
        the sentence or bullet from which it was derived).
    confidence:
        Optional confidence score (0–1 range) representing how strongly the
        underlying model or heuristic supports this item.
    esco_id:
        Optional ESCO skill identifier when the item has been mapped to the
        ESCO taxonomy.
    canonical_key:
        Optional normalized key used for deduplication or canonicalization.
    meta:
        Free-form metadata dictionary for additional attributes (e.g.,
        model version, source flags, debug information).
    """

    name: str
    type: str  # 'knowledge' | 'skill' | 'ability'
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    esco_id: Optional[str] = None
    canonical_key: Optional[str] = None
    meta: Dict = field(default_factory=dict)


@dataclass
class RunReport:
    """
    Summary of a single pipeline run for an AFSC.

    This is useful for both logging/debugging and for displaying status
    information in the Streamlit admin tools.

    Attributes
    ----------
    afsc_code:
        AFSC code processed in this run.
    afsc_title:
        Title of the AFSC at the time of processing.
    counts_by_type:
        Dictionary mapping item types (e.g., "knowledge", "skill", "ability")
        to the number of items produced for each.
    created_items:
        Count of new Item nodes created in the graph (if writing to Neo4j).
    updated_items:
        Count of existing Item nodes that were updated/linked in this run.
    created_edges:
        Count of new relationships (e.g., REQUIRES / ALIGNS_TO) created.
    warnings:
        List of warning messages or non-fatal issues encountered during the run.
    artifacts:
        Free-form dictionary for any additional run artifacts (e.g.,
        raw logs, file paths, debug metrics, or export references).
    """

    afsc_code: str
    afsc_title: str
    counts_by_type: Dict[str, int]
    created_items: int
    updated_items: int
    created_edges: int
    warnings: List[str] = field(default_factory=list)
    artifacts: Dict = field(default_factory=dict)

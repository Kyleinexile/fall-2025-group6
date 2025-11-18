# src/afsc_pipeline/esco_mapper.py
"""
Local ESCO skill mapping for K/S/A items.

This module takes `ItemDraft` objects (Knowledge / Skill / Ability) and tries
to attach ESCO skill IDs by fuzzy-matching item text against a local ESCO
catalog CSV.

Key behaviors
-------------
- Loads a compact ESCO skills catalog once per process from `ESCO_CSV`
  (default: `src/Data/esco/esco_skills.csv`).
- Normalizes both item text and ESCO labels (lowercase, strip punctuation,
  collapse whitespace).
- Computes a hybrid similarity score:
    * token-level Jaccard similarity, and
    * character-level `difflib.SequenceMatcher` ratio.
- Applies different similarity thresholds by item type:
    * Skills:  SIMILARITY_THRESHOLD_SKILL
    * Knowledge: SIMILARITY_THRESHOLD_KNOW
    * Abilities: SIMILARITY_THRESHOLD_ABILITY
- For each item without an ESCO ID, the best candidate above threshold is used
  to set `esco_id` (via a shallow copy of the `ItemDraft`).

Typical usage
-------------
This runs after LAiSER extraction and LLM enhancement, but before dedupe/
canonicalization, to enrich items with standardized ESCO skill identifiers.
"""

from __future__ import annotations

import csv
import os
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# --------------------------
# Config / Paths
# --------------------------
# Default location for your ESCO CSV; override with ESCO_CSV env.
# Expected header (case-insensitive): esco_id, label, alt_labels
# alt_labels: optional; semicolon-separated list of synonyms
DEFAULT_ESCO_CSV = "src/Data/esco/esco_skills.csv"
ESCO_CSV = os.getenv("ESCO_CSV", DEFAULT_ESCO_CSV)

# Matching thresholds (tune as needed)
# Skills tend to be short; use stricter threshold to avoid wrong links.
SIMILARITY_THRESHOLD_SKILL = float(os.getenv("ESCO_SIM_SKILL", "0.90"))
SIMILARITY_THRESHOLD_KNOW = float(os.getenv("ESCO_SIM_KNOW", "0.92"))
SIMILARITY_THRESHOLD_ABILITY = float(os.getenv("ESCO_SIM_ABILITY", "0.90"))

# Guardrail for extremely long alt-label lists in ESCO
MAX_CANDIDATES_PER_LABEL = 8


# --------------------------
# Normalization / Similarity
# --------------------------
_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w\s]")
_prefix_knowledge = re.compile(r"^\s*knowledge\s+of\s+", re.IGNORECASE)
_prefix_ability = re.compile(r"^\s*ability\s+to\s+", re.IGNORECASE)


def _norm(s: str) -> str:
    """
    Normalize a string for matching:
      - strip
      - lowercase
      - remove punctuation
      - collapse whitespace
    """
    s = s.strip().lower()
    s = _punct_re.sub(" ", s)
    s = _ws_re.sub(" ", s)
    return s.strip()


def _tokens(s: str) -> List[str]:
    """Tokenize a normalized string on whitespace."""
    return _norm(s).split()


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """
    Jaccard similarity between two token sets.

    1.0 = identical sets, 0.0 = no overlap.
    """
    A, B = set(a), set(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / max(1, union)


def _difflib(a: str, b: str) -> float:
    """Character-level similarity using difflib.SequenceMatcher."""
    return SequenceMatcher(None, a, b).ratio()


def _hybrid(a: str, b: str) -> float:
    """
    Hybrid similarity for short skill phrases.

    - Normalizes both inputs.
    - Blends token Jaccard (0.6 weight) and difflib ratio (0.4 weight).
    """
    a_n, b_n = _norm(a), _norm(b)
    return 0.6 * _jaccard(_tokens(a_n), _tokens(b_n)) + 0.4 * _difflib(a_n, b_n)


# --------------------------
# ESCO Catalog
# --------------------------
class _ESCOEntry:
    """
    Lightweight in-memory representation of an ESCO skill entry.

    Attributes
    ----------
    esco_id : str
        ESCO skill identifier.
    label : str
        Primary label for the skill.
    alts : List[str]
        Optional alternative labels / synonyms (truncated for safety).
    label_norm : str
        Normalized primary label.
    alts_norm : List[str]
        Normalized alternative labels.
    """

    __slots__ = ("esco_id", "label", "alts", "label_norm", "alts_norm")

    def __init__(self, esco_id: str, label: str, alts: List[str]) -> None:
        self.esco_id = esco_id.strip()
        self.label = label.strip()
        # Truncate alt labels to avoid pathological catalogs
        self.alts = [a.strip() for a in alts if a and a.strip()][:MAX_CANDIDATES_PER_LABEL]
        self.label_norm = _norm(self.label)
        self.alts_norm = [_norm(a) for a in self.alts]


def _load_csv(path: str) -> List[_ESCOEntry]:
    """
    Load ESCO entries from a CSV file.

    The header is matched case-insensitively, expecting:
      - esco_id
      - label
      - alt_labels (optional; semicolon-separated)

    Returns an empty list if the file does not exist.
    """
    if not os.path.exists(path):
        return []
    out: List[_ESCOEntry] = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        # normalize headers
        headers = {k.lower(): k for k in r.fieldnames or []}
        cid = headers.get("esco_id")
        clabel = headers.get("label")
        calts = headers.get("alt_labels") or headers.get("alts") or headers.get("altlabels")

        for row in r:
            esco_id = (row.get(cid) or "").strip() if cid else ""
            label = (row.get(clabel) or "").strip() if clabel else ""
            if not esco_id or not label:
                continue
            alts_raw = (row.get(calts) or "") if calts else ""
            alts = [a.strip() for a in alts_raw.split(";") if a.strip()] if alts_raw else []
            out.append(_ESCOEntry(esco_id, label, alts))
    return out


# Cache catalog in memory once per process
_CATALOG: List[_ESCOEntry] = _load_csv(ESCO_CSV)


# --------------------------
# Matching
# --------------------------
def _strip_prefixes(text: str, t: ItemType) -> str:
    """
    Remove leading "Knowledge of" / "Ability to" where appropriate, so the
    matcher can focus on the core concept or verb phrase.
    """
    if t == ItemType.KNOWLEDGE:
        return _prefix_knowledge.sub("", text).strip()
    if t == ItemType.ABILITY:
        # Keep verb phrase; often free-form, but stripping the prefix helps.
        return _prefix_ability.sub("", text).strip()
    return text.strip()


def _threshold_for_type(t: ItemType) -> float:
    """
    Return the ESCO similarity threshold for the given item type.
    """
    if t == ItemType.KNOWLEDGE:
        return SIMILARITY_THRESHOLD_KNOW
    if t == ItemType.ABILITY:
        return SIMILARITY_THRESHOLD_ABILITY
    return SIMILARITY_THRESHOLD_SKILL


def _best_match(text: str, t: ItemType) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Find the best ESCO match for a given text and ItemType.

    Returns
    -------
    Tuple[Optional[str], float, Optional[str]]
        (esco_id, score, matched_label) or (None, 0.0, None) if below threshold.
    """
    if not _CATALOG or not text or len(text) < 3:
        return (None, 0.0, None)

    q = _strip_prefixes(text, t)
    qn = _norm(q)
    if not qn:
        return (None, 0.0, None)

    best_id: Optional[str] = None
    best_score = 0.0
    best_label: Optional[str] = None

    for e in _CATALOG:
        # compare to canonical label
        s = _hybrid(qn, e.label_norm)
        if s > best_score:
            best_id, best_score, best_label = e.esco_id, s, e.label
        # compare to alt labels
        for alt_norm, alt_raw in zip(e.alts_norm, e.alts):
            s2 = _hybrid(qn, alt_norm)
            if s2 > best_score:
                best_id, best_score, best_label = e.esco_id, s2, alt_raw

    thr = _threshold_for_type(t)
    if best_score >= thr:
        return (best_id, best_score, best_label)
    return (None, best_score, None)


# --------------------------
# Public API
# --------------------------
def map_esco_ids(items: List[ItemDraft]) -> List[ItemDraft]:
    """
    Assign ESCO IDs to items that lack one, using a local ESCO catalog.

    Behavior
    --------
    - If the ESCO catalog is missing/empty, returns the original items unchanged.
    - If an item already has `esco_id`, it is passed through untouched.
    - Otherwise, we:
        * compute the best ESCO match for the item text,
        * check if the score exceeds the type-specific threshold, and
        * if so, return a shallow copy of the item with `esco_id` set.

    Strategy notes
    --------------
    - Skills are often closest to ESCO skill labels, so the threshold is tuned
      to be strict but practical.
    - Knowledge items are matched after removing the "Knowledge of" prefix.
    - Ability items tend to be more free-form; the threshold is set separately
      and may result in fewer matches.

    Parameters
    ----------
    items : List[ItemDraft]
        Items to enrich with ESCO IDs.

    Returns
    -------
    List[ItemDraft]
        New list of items, where some entries may have newly assigned ESCO IDs.
    """
    if not items:
        return []

    updated: List[ItemDraft] = []
    for it in items:
        # Already ESCO-tagged: pass through
        if it.esco_id and str(it.esco_id).strip():
            updated.append(it)
            continue

        # Only attempt mapping if we have a catalog
        if not _CATALOG:
            updated.append(it)
            continue

        esco_id, score, match_label = _best_match(it.text, it.item_type)
        if esco_id:
            # Create shallow copy with esco_id set
            updated.append(ItemDraft(
                text=it.text,
                item_type=it.item_type,
                confidence=it.confidence,
                source=it.source,
                esco_id=esco_id,
            ))
        else:
            updated.append(it)

    return updated

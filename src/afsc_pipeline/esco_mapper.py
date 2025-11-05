# src/afsc_pipeline/esco_mapper.py
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

MAX_CANDIDATES_PER_LABEL = 8  # guardrails for extremely long alt label lists


# --------------------------
# Normalization / Similarity
# --------------------------
_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w\s]")
_prefix_knowledge = re.compile(r"^\s*knowledge\s+of\s+", re.IGNORECASE)
_prefix_ability = re.compile(r"^\s*ability\s+to\s+", re.IGNORECASE)

def _norm(s: str) -> str:
    s = s.strip().lower()
    s = _punct_re.sub(" ", s)
    s = _ws_re.sub(" ", s)
    return s.strip()

def _tokens(s: str) -> List[str]:
    return _norm(s).split()

def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / max(1, union)

def _difflib(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def _hybrid(a: str, b: str) -> float:
    # Weighted blend slightly favoring token overlap
    a_n, b_n = _norm(a), _norm(b)
    return 0.6 * _jaccard(_tokens(a_n), _tokens(b_n)) + 0.4 * _difflib(a_n, b_n)


# --------------------------
# ESCO Catalog
# --------------------------
class _ESCOEntry:
    __slots__ = ("esco_id", "label", "alts", "label_norm", "alts_norm")

    def __init__(self, esco_id: str, label: str, alts: List[str]) -> None:
        self.esco_id = esco_id.strip()
        self.label = label.strip()
        self.alts = [a.strip() for a in alts if a and a.strip()][:MAX_CANDIDATES_PER_LABEL]
        self.label_norm = _norm(self.label)
        self.alts_norm = [_norm(a) for a in self.alts]

def _load_csv(path: str) -> List[_ESCOEntry]:
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
    if t == ItemType.knowledge:
        return _prefix_knowledge.sub("", text).strip()
    if t == ItemType.ability:
        # keep verb phrase; often too free-form to map, but we try
        return _prefix_ability.sub("", text).strip()
    return text.strip()

def _threshold_for_type(t: ItemType) -> float:
    if t == ItemType.knowledge:
        return SIMILARITY_THRESHOLD_KNOW
    if t == ItemType.ability:
        return SIMILARITY_THRESHOLD_ABILITY
    return SIMILARITY_THRESHOLD_SKILL

def _best_match(text: str, t: ItemType) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Returns (esco_id, score, matched_label) or (None, 0.0, None)
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
    Assign ESCO IDs to items that lack one, using a local catalog.
    - No-ops safely if the catalog is missing/empty.
    - Returns NEW ItemDraft copies where an esco_id was added.

    Strategy:
      * Try to map skills first.
      * Map knowledge lines after removing 'Knowledge of ' prefix.
      * Abilities are mapped conservatively (often too free-form).
    """
    if not items:
        return []

    updated: List[ItemDraft] = []
    for it in items:
        if it.esco_id and str(it.esco_id).strip():
            updated.append(it)
            continue

        # Only attempt mapping if we have a catalog
        if not _CATALOG:
            updated.append(it)
            continue

        esco_id, score, match_label = _best_match(it.text, it.item_type)
        if esco_id:
            # Create a shallow copy with esco_id set; preserve content_sig
            updated.append(ItemDraft(
                text=it.text,
                item_type=it.item_type,
                confidence=it.confidence,
                esco_id=esco_id,
                source=it.source,
                content_sig=it.content_sig,
            ))
        else:
            updated.append(it)

    return updated

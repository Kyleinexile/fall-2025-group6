# src/afsc_pipeline/dedupe.py
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# --------- Text normalization helpers ---------

_ws_re = re.compile(r"\s+")
_punct_re = re.compile(r"[^\w\s]")  # remove punctuation except spaces/word chars
_articles_re = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)

def _normalize_for_match(text: str) -> str:
    """
    Lightweight normalization that’s robust to punctuation/case/whitespace noise.
    Does NOT return a value used for IDs—only for similarity checks.
    """
    t = text.strip().lower()
    t = _punct_re.sub(" ", t)
    t = _ws_re.sub(" ", t)
    return t.strip()

def _tokenize(text: str) -> List[str]:
    """Simple whitespace tokenization after normalization."""
    return _normalize_for_match(text).split()

def _jaccard(a_tokens: Iterable[str], b_tokens: Iterable[str]) -> float:
    a_set = set(a_tokens)
    b_set = set(b_tokens)
    if not a_set and not b_set:
        return 1.0
    if not a_set or not b_set:
        return 0.0
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / max(1, union)

def _difflib_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def _hybrid_similarity(a: str, b: str) -> float:
    """
    Blend of token Jaccard and character-level difflib ratio.
    Works well for short KSA phrases with small lexical variations.
    """
    a_norm = _normalize_for_match(a)
    b_norm = _normalize_for_match(b)
    j = _jaccard(_tokenize(a_norm), _tokenize(b_norm))
    d = _difflib_ratio(a_norm, b_norm)
    # Weighted blend: emphasize token overlap slightly more than char overlap
    return 0.6 * j + 0.4 * d


# --------- Canonicalization / Clustering ---------

def _quality_tuple(it: ItemDraft) -> Tuple[int, float, int, int]:
    """
    Sorting key to pick the best representative in a duplicate cluster:
      - has_esco (1/0) desc
      - confidence desc
      - source_is_laiser (1/0) desc
      - text_len desc (weak tiebreaker)
    """
    has_esco = 1 if (it.esco_id and str(it.esco_id).strip()) else 0
    source_laiser = 1 if (it.source or "").lower() == "laiser" else 0
    return (has_esco, float(it.confidence), source_laiser, len(it.text or ""))

def canonicalize_items(
    items: List[ItemDraft],
    *,
    similarity_threshold: float = 0.86,
    min_text_len: int = 4,
) -> List[ItemDraft]:
    """
    Group near-duplicate items **within the same item_type** and return one canonical item per group.

    - Similarity uses a hybrid of token Jaccard and difflib ratio.
    - Winner selection prefers ESCO presence, higher confidence, LAiSER source, then longer text.
    - If any member of a cluster has an ESCO id, we lift it onto the selected winner.
    - We do NOT change text or content_sig (idempotent for graph writes).

    Parameters
    ----------
    items : List[ItemDraft]
        Extracted items (possibly with duplicates/near-duplicates).
    similarity_threshold : float
        0..1, where larger is stricter. 0.86 is a good default for short KSA phrases.
    min_text_len : int
        Skip fuzzy comparisons for trivially short strings (under this length).

    Returns
    -------
    List[ItemDraft]
        Canonicalized items.
    """
    if not items:
        return []

    # Partition by type so we only compare like-for-like
    by_type: dict[ItemType, List[ItemDraft]] = {}
    for it in items:
        by_type.setdefault(it.item_type, []).append(it)

    canonical: List[ItemDraft] = []

    for t, bucket in by_type.items():
        # Stable sort with best-first according to our quality tuple
        ordered = sorted(bucket, key=_quality_tuple, reverse=True)

        # Each cluster holds representative index and members
        clusters: List[List[int]] = []  # list of lists of indices into ordered

        for idx, it in enumerate(ordered):
            placed = False
            if len((it.text or "")) >= min_text_len:
                for cluster in clusters:
                    rep_idx = cluster[0]
                    rep = ordered[rep_idx]
                    sim = _hybrid_similarity(it.text, rep.text)
                    if sim >= similarity_threshold:
                        cluster.append(idx)
                        placed = True
                        break
            if not placed:
                clusters.append([idx])

        # Choose winner for each cluster (first element given ordered best-first)
        for cluster in clusters:
            winner = ordered[cluster[0]]
            # Lift any available ESCO id from the cluster if winner lacks one
            if not (winner.esco_id and str(winner.esco_id).strip()):
                for j in cluster[1:]:
                    maybe = ordered[j]
                    if maybe.esco_id and str(maybe.esco_id).strip():
                        # Create a shallow copy with esco_id lifted; preserve content_sig
                        winner = ItemDraft(
                            text=winner.text,
                            item_type=winner.item_type,
                            confidence=winner.confidence,
                            esco_id=maybe.esco_id,
                            source=winner.source,
                            content_sig=winner.content_sig,
                        )
                        break
            canonical.append(winner)

    return canonical

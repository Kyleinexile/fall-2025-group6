# src/afsc_pipeline/dedupe.py
"""
Fuzzy deduplication and canonicalization of KSA items.

This module:
- Normalizes short KSA phrases (lowercasing, stripping punctuation/whitespace).
- Computes a hybrid similarity score combining:
    * token-level Jaccard similarity, and
    * character-level difflib ratio.
- Clusters near-duplicate items **within the same ItemType**.
- Picks a canonical representative per cluster (preferring ESCO-tagged,
  higher-confidence, LAiSER-sourced, longer-text items).
- Optionally lifts ESCO IDs from any cluster member onto the chosen winner.

Usage
-----
Typically called from the pipeline after:
- `quality_filter.apply_quality_filter` has pruned obvious noise, and
- `enhance_llm.enhance_items_with_llm` has added K/A items.

The goal is to reduce redundancy before writing to Neo4j while preserving
the strongest, most informative version of each concept.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# --------- Text normalization helpers ---------

# Collapse multiple whitespace runs into a single space
_ws_re = re.compile(r"\s+")
# Remove punctuation while keeping word characters and spaces
_punct_re = re.compile(r"[^\w\s]")  # remove punctuation except spaces/word chars
# (Not currently used, but kept as a helper if we later strip articles like "the")
_articles_re = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)


def _normalize_for_match(text: str) -> str:
    """
    Lightweight normalization for similarity checks.

    Robust to:
    - Case differences
    - Punctuation noise
    - Extra/misplaced whitespace

    Note
    ----
    This is **not** used as a persistent canonical key or ID, only for
    computing similarity between two strings.
    """
    t = text.strip().lower()
    t = _punct_re.sub(" ", t)
    t = _ws_re.sub(" ", t)
    return t.strip()


def _tokenize(text: str) -> List[str]:
    """
    Whitespace tokenization on a normalized string.

    Returns
    -------
    List[str]
        List of word tokens after normalization.
    """
    return _normalize_for_match(text).split()


def _jaccard(a_tokens: Iterable[str], b_tokens: Iterable[str]) -> float:
    """
    Compute Jaccard similarity between two token sets.

    1.0 = identical token sets
    0.0 = no overlap
    """
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
    """
    Thin wrapper around difflib.SequenceMatcher for character-level similarity.
    """
    return SequenceMatcher(None, a, b).ratio()


def _hybrid_similarity(a: str, b: str) -> float:
    """
    Blend token Jaccard and character-level difflib ratio.

    This works well for:
    - Short KSA phrases,
    - Minor wording differences,
    - Small word reorderings.

    Returns
    -------
    float
        Weighted blend in [0, 1], with token overlap emphasized slightly more.
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
    Sorting key to pick the best representative in a duplicate cluster.

    Priority (higher is better):
      1. has_esco        : 1 if item has an ESCO ID, else 0
      2. confidence      : numeric confidence score
      3. source_is_laiser: 1 if source=='laiser', else 0
      4. text_len        : length of text (longer is a weak tiebreaker)

    This key is used in descending order so that the "best" item appears first.
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

    Algorithm outline
    -----------------
    1. Partition items by `ItemType` (e.g., Knowledge vs Skill).
    2. Within each type:
       - Sort items best-first according to `_quality_tuple`.
       - Iterate items and either:
           * Attach them to an existing cluster if they are
             `>= similarity_threshold` similar to the cluster representative, or
           * Start a new cluster.
    3. For each cluster:
       - Pick the first item (best according to sort order) as the winner.
       - If the winner lacks an ESCO ID, but another cluster member has one,
         lift that ESCO ID onto a shallow copy of the winner.
       - Append the winner to the canonical result list.

    Important:
    ----------
    - Similarity uses a hybrid of token Jaccard and difflib ratio.
    - Winner selection prefers:
        ESCO presence > higher confidence > LAiSER source > longer text.
    - If any cluster member has an ESCO ID, we *propagate* it to the winner.
    - We do NOT change the text of winners (so graph writes remain idempotent).

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
        Canonicalized items; each represents a cluster of similar items.
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

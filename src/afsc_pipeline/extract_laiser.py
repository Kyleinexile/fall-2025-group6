# src/afsc_pipeline/extract_laiser.py
"""
Skill extraction layer for the AFSC → KSA pipeline.

This module is responsible for generating initial SKILL candidates from
cleaned AFSC text. It supports two modes:

1. Primary LAiSER-based extraction
   - Uses the LAiSER SkillExtractorRefactored with a Gemini backend
   - Aligns free-text skill phrases to a skill taxonomy and ESCO IDs

2. Fallback pattern-based extraction
   - When LAiSER is disabled or unavailable, uses regex heuristics to
     extract verb–object phrases and domain-specific terms.

Downstream components (LLM enhancement, dedupe, ESCO mapper, graph writer)
treat these outputs as `ItemDraft` objects with type = SKILL.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Core item types and draft representation
# ---------------------------------------------------------------------------


class ItemType(str, Enum):
    """
    Enum representing the high-level item categories.

    This is the minimal type system used at the extraction stage. Later
    pipeline steps (LLM enhancement, quality filtering) may convert or
    extend these, but here we primarily produce SKILL items.

    Values
    ------
    KNOWLEDGE:
        Conceptual knowledge (typically LLM-generated).
    SKILL:
        Action-oriented skill or competency (primarily LAiSER-derived).
    ABILITY:
        Cognitive / operational ability (typically LLM-generated).
    """

    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ABILITY = "ability"


@dataclass
class ItemDraft:
    """
    Lightweight representation of an extracted item before final cleanup.

    At this stage, items are considered "drafts" and may still be filtered,
    deduplicated, or enriched (e.g., with ESCO alignment) before being
    promoted to full KSA items.

    Attributes
    ----------
    text:
        The human-readable text of the item (e.g., "conduct target analysis").
    item_type:
        Category of the item (here, almost always ItemType.SKILL).
    confidence:
        Confidence score from the extractor or heuristic (0–1 range).
    source:
        Short label indicating which component produced the item
        (e.g., "laiser-gemini", "fallback-pattern", "fallback-domain").
    esco_id:
        Optional ESCO identifier, when available from LAiSER alignment.
    """

    text: str
    item_type: ItemType
    confidence: float = 0.0
    source: str = "unknown"
    esco_id: Optional[str] = None


# ---------------------------------------------------------------------------
# LAiSER-backed extraction
# ---------------------------------------------------------------------------


def _build_extractor():
    """
    Initialize the LAiSER SkillExtractorRefactored with a Gemini backend.

    The GEMINI_API_KEY environment variable must be set for this to succeed.
    If initialization fails for any reason, the function logs the error and
    returns None, allowing the caller to fall back gracefully.

    Returns
    -------
    SkillExtractorRefactored | None
        A configured LAiSER extractor instance, or None if initialization fails.
    """
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored

        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            print("[LAISER] No GEMINI_API_KEY found")
            return None

        print("[LAISER] Initializing with Gemini API...")
        return SkillExtractorRefactored(
            model_id="gemini",
            api_key=gemini_key,
            use_gpu=False,
        )
    except Exception as e:
        print(f"[LAISER] Could not init: {e}")
        import traceback

        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Fallback heuristic extraction
# ---------------------------------------------------------------------------


def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    """
    Heuristic skill extraction used when LAiSER is disabled or unavailable.

    This approach relies on simple pattern matching over the cleaned AFSC
    text to extract verb–object phrases and domain-specific skill phrases.
    It is intentionally conservative and bounded in the number of items
    it returns, but provides a reasonable set of SKILL candidates when
    the primary LAiSER path is not available.

    Parameters
    ----------
    clean_text:
        Preprocessed AFSC text (see `clean_afsc_text` in preprocess.py).

    Returns
    -------
    List[ItemDraft]
        A small list of draft SKILL items derived from the text.
    """
    items: List[ItemDraft] = []

    # Common action verbs indicating skills
    action_verbs = [
        "perform",
        "conduct",
        "analyze",
        "develop",
        "manage",
        "coordinate",
        "evaluate",
        "assess",
        "prepare",
        "produce",
        "execute",
        "direct",
        "integrate",
        "synthesize",
        "collect",
        "process",
        "disseminate",
        "target",
        "exploit",
        "brief",
        "maintain",
        "establish",
        "implement",
        "monitor",
        "support",
        "plan",
        "organize",
        "identify",
        "determine",
    ]

    # Extract verb + object phrases
    for verb in action_verbs:
        # Look for verb + 2–4 word phrases
        pattern = rf"\b{verb}(?:s|es|ing)?\s+([a-z]+\s+[a-z]+(?:\s+[a-z]+){{0,2}})\b"
        matches = re.findall(pattern, clean_text.lower())

        for phrase in matches:
            phrase = phrase.strip()
            # Skip common filler phrases
            if any(skip in phrase for skip in ["and the", "or the", "of the", "to the"]):
                continue
            if len(phrase) > 15:
                skill_text = f"{verb} {phrase}"
                # Remove trailing conjunctions/prepositions
                skill_text = re.sub(
                    r"\s+(and|or|the|for|with|from)$", "", skill_text
                )
                items.append(
                    ItemDraft(
                        text=skill_text,
                        item_type=ItemType.SKILL,
                        confidence=0.55,
                        source="fallback-pattern",
                        esco_id=None,
                    )
                )
                if len(items) >= 8:
                    break
        if len(items) >= 8:
            break

    # Extract phrases with domain keywords
    domain_keywords = [
        "intelligence",
        "analysis",
        "targeting",
        "collection",
        "exploitation",
        "assessment",
        "planning",
        "operations",
        "coordination",
        "management",
        "briefing",
        "reporting",
        "evaluation",
        "integration",
        "production",
    ]

    # Only add domain patterns if we have fewer than 4 verb-based skills
    if len(items) < 4:
        for keyword in domain_keywords:
            pattern = rf"\b([a-z]+\s+){keyword}(\s+[a-z]+)?\b"
            matches = re.findall(pattern, clean_text.lower())
            for match in matches[:1]:
                phrase = "".join([m for m in match if m]).strip()
                if 15 <= len(phrase) <= 60 and "  " not in phrase:
                    items.append(
                        ItemDraft(
                            text=phrase,
                            item_type=ItemType.SKILL,
                            confidence=0.50,
                            source="fallback-domain",
                            esco_id=None,
                        )
                    )

    # Deduplicate by normalized text
    seen = set()
    unique_items: List[ItemDraft] = []
    for item in items:
        key = item.text.lower().strip()
        if key not in seen and len(key) > 8:
            seen.add(key)
            unique_items.append(item)
            if len(unique_items) >= 6:
                break

    # Generic fallback if nothing found
    if not unique_items:
        unique_items = [
            ItemDraft(
                text="intelligence analysis",
                item_type=ItemType.SKILL,
                confidence=0.3,
                source="fallback-generic",
                esco_id=None,
            ),
            ItemDraft(
                text="data processing",
                item_type=ItemType.SKILL,
                confidence=0.3,
                source="fallback-generic",
                esco_id=None,
            ),
        ]

    return unique_items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    """
    Main entry point for extracting SKILL items from AFSC text.

    This function orchestrates the decision between LAiSER-based extraction
    and the heuristic fallback:

    - If USE_LAISER is false (or unset), the heuristic path is used.
    - If USE_LAISER is true, the function attempts to initialize LAiSER and
      call `align_skills` with a set of candidate phrases.
    - If LAiSER fails at any point, the function logs the error and falls
      back to the heuristic extractor.

    Parameters
    ----------
    clean_text:
        Preprocessed AFSC text (a single narrative block).

    Returns
    -------
    List[ItemDraft]
        A list of SKILL items with confidence scores and optional ESCO IDs.
    """
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))
    print(f"[LAISER] Enabled={use_laiser}, TopK={top_k}")

    if not use_laiser:
        print("[LAISER] Using fallback extraction (USE_LAISER=false)")
        return _fallback_extract(clean_text)

    extractor = _build_extractor()
    if not extractor:
        print("[LAISER] Extractor failed to initialize, using fallback")
        return _fallback_extract(clean_text)

    # Split text into phrases
    raw_candidates: List[str] = []
    for seg in re.split(r"[;\n\.\u2022,]", clean_text):
        c = seg.strip()
        if c.lower().startswith(
            ("duties", "knowledge", "skills", "abilities")
        ):
            continue
        if 4 <= len(c) < 100:
            raw_candidates.append(c)

    if not raw_candidates:
        raw_candidates = [
            "imagery exploitation",
            "geospatial intelligence",
            "target development",
        ]

    # Deduplicate while preserving order, and cap the candidate list
    raw_candidates = list(dict.fromkeys(raw_candidates))[:50]
    print(f"[LAISER] Extracted {len(raw_candidates)} candidate phrases")

    # Call align_skills with Gemini
    try:
        print("[LAISER] Calling align_skills...")
        result_df = extractor.align_skills(
            raw_skills=raw_candidates,
            document_id="AFSC-0",
        )
        print(f"[LAISER] Got {len(result_df)} results from align_skills")
    except Exception as e:
        print(f"[LAISER] Error during align_skills: {e}")
        import traceback

        traceback.print_exc()
        return _fallback_extract(clean_text)

    if result_df.empty:
        print("[LAISER] Empty results, using fallback")
        return _fallback_extract(clean_text)

    # Parse results
    items: List[ItemDraft] = []
    for idx, row in result_df.iterrows():
        txt = str(
            row.get("Taxonomy Skill") or row.get("Description") or ""
        ).strip()
        if not txt:
            continue

        conf = float(row.get("Correlation Coefficient") or 0.5)
        esco_id = str(row.get("Skill Tag") or "").strip() or None

        if esco_id:
            print(f"[LAISER] ✓ {txt[:50]} -> {esco_id} (conf={conf:.3f})")

        items.append(
            ItemDraft(
                text=txt,
                item_type=ItemType.SKILL,
                confidence=conf,
                source="laiser-gemini",
                esco_id=esco_id,
            )
        )

    if items:
        items.sort(key=lambda x: x.confidence, reverse=True)
        items = items[:top_k]

    esco_count = sum(1 for i in items if i.esco_id)
    print(
        f"[LAISER] Returning {len(items)} skills ({esco_count} with ESCO IDs)"
    )

    return items if items else _fallback_extract(clean_text)

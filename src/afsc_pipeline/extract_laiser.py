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
      call either `extract_skills` (new API) or `extract_and_align` (batch API)
      on the full AFSC text.
    - If LAiSER fails at any point, the function logs the error and falls
      back to the heuristic extractor.
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

    # ---- DEBUG: what does this object actually look like? ----
    try:
        methods = [m for m in dir(extractor) if not m.startswith("_")]
        print(f"[LAISER] SkillExtractorRefactored type: {type(extractor)}")
        print(f"[LAISER] Available public methods: {methods}")
    except Exception as e:
        print(f"[LAISER] Error introspecting extractor: {e}")

    # Decide which LAiSER interface is available
    has_extract_skills = hasattr(extractor, "extract_skills")
    has_extract_and_align = hasattr(extractor, "extract_and_align")
    print(
        f"[LAISER] has_extract_skills={has_extract_skills}, "
        f"has_extract_and_align={has_extract_and_align}"
    )

    try:
        if has_extract_skills:
            # New refactored API – single text
            print(
                "[LAISER] Using SkillExtractorRefactored.extract_skills "
                "(method='ksa', input_type='job_desc')"
            )
            laiser_result = extractor.extract_skills(
                clean_text,
                method="ksa",
                input_type="job_desc",
            )

        elif has_extract_and_align:
            # Older refactored API – batch DataFrame
            print(
                "[LAISER] Using SkillExtractorRefactored.extract_and_align "
                "with a single-row DataFrame (input_type='job_desc')"
            )
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                [{"job_id": "AFSC-0", "description": clean_text}]
            )
            laiser_result = extractor.extract_and_align(
                df,
                id_column="job_id",
                text_columns=["description"],
                input_type="job_desc",
            )

        else:
            print(
                "[LAISER] No compatible methods on SkillExtractorRefactored "
                "(missing extract_skills/extract_and_align); using fallback"
            )
            return _fallback_extract(clean_text)

    except Exception as e:
        print(f"[LAISER] Error during LAiSER extraction: {e}")
        import traceback

        traceback.print_exc()
        return _fallback_extract(clean_text)

    if laiser_result is None:
        print("[LAISER] LAiSER returned None, using fallback")
        return _fallback_extract(clean_text)

    # We try to be robust: handle DataFrame, list[dict], or similar structures
    items: List[ItemDraft] = []

    try:
        import pandas as pd  # type: ignore

        if isinstance(laiser_result, pd.DataFrame):
            df = laiser_result
            print(f"[LAISER] Result is DataFrame with columns: {list(df.columns)}")
        else:
            print(f"[LAISER] Result type is {type(laiser_result)}, coercing to DataFrame")
            df = pd.DataFrame(laiser_result)
            print(f"[LAISER] Coerced DataFrame columns: {list(df.columns)}")
    except Exception as e:
        print(f"[LAISER] Could not interpret LAiSER result: {e}")
        return _fallback_extract(clean_text)

    if df.empty:
        print("[LAISER] Empty LAiSER result DataFrame, using fallback")
        return _fallback_extract(clean_text)

    for _, row in df.iterrows():
        # Try several possible text fields LAiSER might use
        txt = str(
            row.get("Taxonomy Skill")
            or row.get("Description")
            or row.get("Raw Skill")
            or row.get("Skill")
            or ""
        ).strip()
        if not txt:
            continue

        # Confidence / score field can have different names
        conf_val = (
            row.get("Correlation Coefficient")
            or row.get("score")
            or row.get("confidence")
            or 0.5
        )
        try:
            conf = float(conf_val)
        except Exception:
            conf = 0.5

        # ESCO / taxonomy ID
        esco_id_raw = (
            row.get("Skill Tag")
            or row.get("ESCO ID")
            or row.get("esco_id")
            or ""
        )
        esco_id = str(esco_id_raw).strip() or None

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

    if not items:
        print("[LAISER] No usable rows in LAiSER result, using fallback")
        return _fallback_extract(clean_text)

    # Sort and cap like before
    items.sort(key=lambda x: x.confidence, reverse=True)
    items = items[:top_k]

    esco_count = sum(1 for i in items if i.esco_id)
    print(
        f"[LAISER] Returning {len(items)} skills ({esco_count} with ESCO IDs) "
        "from LAiSER"
    )

    return items if items else _fallback_extract(clean_text)

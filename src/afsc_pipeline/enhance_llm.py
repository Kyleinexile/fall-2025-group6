# src/afsc_pipeline/enhance_llm.py
"""
LLM-based enhancement for K/A (Knowledge / Ability) items with graceful fallbacks.

Purpose
-------
- Take raw extracted items (often skill-heavy) and enrich with:
  * Additional Knowledge statements
  * Additional Ability statements
- Keep pipeline resilient if no keys/services are available:
  * Falls back to deterministic, dependency-free heuristics.

Environment (all optional)
--------------------------
LLM_PROVIDER=gemini|anthropic|disabled   (default: disabled)
LLM_MODEL_GEMINI=gemini-1.5-flash        (free tier: 15 RPM)
LLM_MODEL_ANTHROPIC=claude-3-5-sonnet-20241022

# API Keys (required if provider is enabled):
GOOGLE_API_KEY=<your-key>
ANTHROPIC_API_KEY=<your-key>

Usage
-----
1. Set LLM_PROVIDER=gemini (or anthropic)
2. Set corresponding API key
3. Pipeline will automatically enhance with K/A
4. Falls back to heuristics if API fails or quota exceeded
"""

from __future__ import annotations

import os
import re
import hashlib
import time
from typing import Iterable, List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# -------------------------
# Config
# -------------------------
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "disabled").strip().lower()
LLM_MODEL_GEMINI = os.getenv("LLM_MODEL_GEMINI", "gemini-1.5-flash")  # Free tier!
LLM_MODEL_ANTHROPIC = os.getenv("LLM_MODEL_ANTHROPIC", "claude-3-5-sonnet-20241022")

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def _sig(text: str, t: ItemType, tag: str = "llm-v1") -> str:
    h = hashlib.sha256()
    h.update(tag.encode())
    h.update(b"|")
    h.update(t.value.encode())
    h.update(b"|")
    h.update(text.encode())
    return h.hexdigest()[:16]


# -------------------------
# Utility: simple noun phrase mining (no deps)
# -------------------------
_word = r"[A-Za-z0-9/\-\+]+"
_cap = r"[A-Z][a-zA-Z0-9/\-\+]+"
def _topical_candidates(text: str, max_items: int = 8) -> List[str]:
    """
    Cheap 'noun-y' phrase finder for Knowledge stubs when LLMs are off.
    Prefers Capitalized Multi-Word sequences and common domain collocations.
    """
    if not text:
        return []

    # capitalize-based multi-word sequences
    caps = re.findall(rf"\b({_cap}(?:\s+{_cap}){{0,3}})\b", text)
    # domain-ish collocations
    collos = re.findall(rf"\b({_word}\s+(analysis|intelligence|security|threats|operations|collection|targeting|briefing|reporting))\b", text, flags=re.IGNORECASE)
    collos = [c[0] for c in collos]
    cand = [c.strip() for c in caps + collos]
    # de-dup while preserving order
    seen = set()
    out = []
    for c in cand:
        k = c.lower()
        if k not in seen and len(k) > 3:
            out.append(c)
            seen.add(k)
        if len(out) >= max_items:
            break
    return out


# -------------------------
# Heuristic enhancement (always available)
# -------------------------
def _heuristic_enhance(afsc_text: str, items: List[ItemDraft]) -> List[ItemDraft]:
    """
    - If K or A are missing/scarce, generate a few plausible K/A statements.
    - Derive Abilities from imperative Skill verbs ('analyze' -> 'Ability to analyze ...').
    - Derive Knowledge from detected 'noun-y' topics in the AFSC text.
    """
    have_k = any(it.item_type == ItemType.KNOWLEDGE for it in items)
    have_a = any(it.item_type == ItemType.ABILITY for it in items)

    new_items: List[ItemDraft] = []

    # Ability from existing skills
    if not have_a:
        # find 1-2 good verbs from existing skills
        verbs = []
        for it in items:
            if it.item_type != ItemType.SKILL:
                continue
            first = it.text.split()[0].lower() if it.text else ""
            # simple verb-ish whitelist
            if first in {"analyze", "conduct", "synthesize", "assess", "brief", "collect", "evaluate", "integrate", "develop"}:
                verbs.append(it.text)
        verbs = verbs[:2]
        for v in verbs:
            text = f"Ability to {v[0].lower() + v[1:]}" if v else "Ability to perform core tasks"
            new_items.append(ItemDraft(
                text=text,
                item_type=ItemType.ABILITY,
                confidence=0.55,
                source="llm-heuristic",
                esco_id=None,
            ))

    # Knowledge from topical candidates
    if not have_k:
        topics = _topical_candidates(afsc_text, max_items=3)
        for t in topics:
            text = f"Knowledge of {t}"
            new_items.append(ItemDraft(
                text=text,
                item_type=ItemType.KNOWLEDGE,
                confidence=0.55,
                source="llm-heuristic",
                esco_id=None,
            ))

    return new_items


# -------------------------
# LLM Implementations
# -------------------------
def _call_llm_gemini(prompt: str) -> str:
    """
    Call Google Gemini API (free tier: gemini-1.5-flash with 15 RPM).
    """
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set")
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(LLM_MODEL_GEMINI)
        
        # Generate with safety settings relaxed for military content
        response = model.generate_content(
            prompt,
            safety_settings={
                'HARASSMENT': 'BLOCK_NONE',
                'HATE_SPEECH': 'BLOCK_NONE',
                'SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                'DANGEROUS_CONTENT': 'BLOCK_NONE',
            }
        )
        
        return response.text
        
    except ImportError:
        raise ImportError("google-generativeai not installed. Run: pip install google-generativeai")
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


def _call_llm_anthropic(prompt: str) -> str:
    """
    Call Anthropic Claude API as fallback.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        message = client.messages.create(
            model=LLM_MODEL_ANTHROPIC,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
        
    except ImportError:
        raise ImportError("anthropic not installed. Run: pip install anthropic")
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


def _provider_call(prompt: str) -> str:
    """
    Call configured LLM provider with automatic fallback.
    """
    if LLM_PROVIDER == "gemini":
        try:
            return _call_llm_gemini(prompt)
        except Exception as e:
            print(f"⚠️ Gemini failed ({e}), trying Anthropic fallback...")
            if ANTHROPIC_API_KEY:
                try:
                    return _call_llm_anthropic(prompt)
                except Exception as e2:
                    print(f"⚠️ Anthropic also failed ({e2}), using heuristics")
                    return ""
            return ""
    
    elif LLM_PROVIDER == "anthropic":
        try:
            return _call_llm_anthropic(prompt)
        except Exception as e:
            print(f"⚠️ Anthropic failed ({e}), using heuristics")
            return ""
    
    # disabled -> no call
    return ""


# -------------------------
# Prompt + parse
# -------------------------
_PROMPT = """You are assisting with extracting additional Knowledge and Ability statements from an Air Force specialty description.
Return ONLY bullet lines, no prose. Each line must start with a dash and be short (<= 120 chars).
Write 3-6 lines, favoring missing types (Knowledge/Ability). Avoid duplicates. No Skills unless absolutely necessary.

AFSC TEXT:
\"\"\"{afsc_text}\"\"\"

EXISTING ITEMS:
{existing}

FORMAT EXAMPLE:
- Knowledge of intelligence cycle fundamentals
- Ability to synthesize multi-source findings under time constraints
- Knowledge of geospatial analysis techniques"""

def _format_existing(items: List[ItemDraft]) -> str:
    lines = []
    for it in items:
        lines.append(f"- [{it.item_type.value}] {it.text}")
    return "\n".join(lines) if lines else "- (none)"


def _parse_llm_lines(raw: str) -> List[Tuple[ItemType, str]]:
    """
    Parse LLM output lines into (type, text).
    If type not stated, default to Knowledge when line starts with 'Knowledge of',
    Ability when starts with 'Ability to', else skip to keep precision high.
    """
    out: List[Tuple[ItemType, str]] = []
    if not raw:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        # explicit tag?
        m = re.match(r"\[(knowledge|skill|ability)\]\s+(.*)$", line, re.IGNORECASE)
        if m:
            t = ItemType(m.group(1).upper())
            text = m.group(2).strip().rstrip(".")
        else:
            txt = line.rstrip(".")
            low = txt.lower()
            if low.startswith("knowledge of "):
                t = ItemType.KNOWLEDGE
                text = txt
            elif low.startswith("ability to "):
                t = ItemType.ABILITY
                text = txt
            else:
                # skip ambiguous lines to avoid polluting graph
                continue
        if len(text) >= 4:
            out.append((t, text))
    return out


# -------------------------
# Public API
# -------------------------
def enhance_items_with_llm(
    afsc_code: str,
    afsc_text: str,
    items: List[ItemDraft],
    *,
    max_new: int = 6,
) -> List[ItemDraft]:
    """
    Optionally enrich the set with K/A from an LLM; fall back to deterministic heuristics.

    Returns only the NEW items; caller should extend and then dedupe.
    
    Args:
        afsc_code: AFSC identifier (e.g., "1N0X1")
        afsc_text: Full AFSC description text
        items: Existing ItemDraft objects (usually from LAiSER)
        max_new: Maximum new items to generate
        
    Returns:
        List of NEW ItemDraft objects to add to the collection
    """
    # If provider disabled, do heuristic only
    if LLM_PROVIDER in {"", "disabled", "off", "false", "0"}:
        print(f"[LLM] Provider disabled, using heuristics for {afsc_code}")
        return _heuristic_enhance(afsc_text, items)

    prompt = _PROMPT.format(
        afsc_text=afsc_text.strip()[:2000],  # Limit context to avoid token issues
        existing=_format_existing(items),
    )

    try:
        print(f"[LLM] Calling {LLM_PROVIDER} for {afsc_code}...")
        raw = _provider_call(prompt)
        
        if not raw:
            # Fallback to heuristics if LLM returns nothing
            print(f"[LLM] No response, using heuristics for {afsc_code}")
            return _heuristic_enhance(afsc_text, items)
        
        # Parse LLM response
        parsed = _parse_llm_lines(raw)
        new_items = []
        
        for item_type, text in parsed[:max_new]:
            new_items.append(ItemDraft(
                text=text,
                item_type=item_type,
                confidence=0.70,  # LLM-generated gets higher confidence than heuristics
                source=f"llm-{LLM_PROVIDER}",
                esco_id=None,
            ))
        
        print(f"[LLM] Generated {len(new_items)} new items for {afsc_code}")
        return new_items
        
    except Exception as e:
        print(f"[LLM] Error for {afsc_code}: {e}")
        print(f"[LLM] Falling back to heuristics")
        return _heuristic_enhance(afsc_text, items)


# -------------------------
# Test function
# -------------------------
if __name__ == "__main__":
    # Test with sample data
    sample_text = """
    Performs and manages intelligence targeting operations and training.
    Performs intelligence data analysis. Determines intelligence
    information requirements. Analyzes data from multiple sources.
    Identifies targets. Prepares intelligence assessments and reports.
    """
    
    # Simulate LAiSER output (skills only)
    sample_items = [
        ItemDraft(
            text="intelligence data analysis",
            item_type=ItemType.SKILL,
            confidence=0.65,
            source="laiser",
            esco_id="ESCO.1234"
        ),
        ItemDraft(
            text="prepare intelligence reports",
            item_type=ItemType.SKILL,
            confidence=0.58,
            source="laiser",
            esco_id=None
        ),
    ]
    
    print("=" * 60)
    print("Testing LLM Enhancement")
    print("=" * 60)
    print(f"Provider: {LLM_PROVIDER}")
    print(f"Existing items: {len(sample_items)}")
    print()
    
    new_items = enhance_items_with_llm(
        afsc_code="1N0X1",
        afsc_text=sample_text,
        items=sample_items,
    )
    
    print(f"\n✅ Generated {len(new_items)} new items:")
    for item in new_items:
        print(f"  [{item.item_type.value:10}] {item.text} (conf={item.confidence:.2f}, src={item.source})")

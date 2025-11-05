# src/afsc_pipeline/enhance_llm.py
"""
LLM-based enhancement for K/A (Knowledge / Ability) items with graceful fallbacks.
"""

from __future__ import annotations

import os
import re
import hashlib
from typing import List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# -------------------------
# Config
# -------------------------
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()  # Default to OpenAI
LLM_MODEL_GEMINI = os.getenv("LLM_MODEL_GEMINI", "gemini-2.0-flash")
LLM_MODEL_ANTHROPIC = os.getenv("LLM_MODEL_ANTHROPIC", "claude-3-sonnet-20240229")
LLM_MODEL_OPENAI = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# -------------------------
# Utility: simple noun phrase mining
# -------------------------
_word = r"[A-Za-z0-9/\-\+]+"
_cap = r"[A-Z][a-zA-Z0-9/\-\+]+"

def _topical_candidates(text: str, max_items: int = 8) -> List[str]:
    """Extract noun-like phrases for Knowledge generation."""
    if not text:
        return []
    
    caps = re.findall(rf"\b({_cap}(?:\s+{_cap}){{0,3}})\b", text)
    collos = re.findall(rf"\b({_word}\s+(analysis|intelligence|security|threats|operations|collection|targeting|briefing|reporting))\b", text, flags=re.IGNORECASE)
    collos = [c[0] for c in collos]
    cand = [c.strip() for c in caps + collos]
    
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
# Heuristic enhancement
# -------------------------
def _heuristic_enhance(afsc_text: str, items: List[ItemDraft]) -> List[ItemDraft]:
    """Generate K/A from heuristics when LLM unavailable."""
    have_k = any(it.item_type == ItemType.KNOWLEDGE for it in items)
    have_a = any(it.item_type == ItemType.ABILITY for it in items)
    
    new_items: List[ItemDraft] = []
    
    # Abilities from skill verbs
    if not have_a:
        verbs = []
        for it in items:
            if it.item_type != ItemType.SKILL:
                continue
            first = it.text.split()[0].lower() if it.text else ""
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
    
    # Knowledge from topics
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
    """Call Google Gemini API with proper safety settings."""
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set")
    
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(LLM_MODEL_GEMINI)
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        response = model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        return response.text
        
    except ImportError:
        raise ImportError("google-generativeai not installed")
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


def _call_llm_anthropic(prompt: str) -> str:
    """Call Anthropic Claude API."""
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
        raise ImportError("anthropic not installed")
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


def _call_llm_openai(prompt: str) -> str:
    """Call OpenAI API."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model=LLM_MODEL_OPENAI,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=512,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except ImportError:
        raise ImportError("openai not installed")
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")


def _provider_call(prompt: str) -> str:
    """Call LLM with automatic fallback."""
    if LLM_PROVIDER == "openai":
        try:
            return _call_llm_openai(prompt)
        except Exception as e:
            print(f"[WARNING] OpenAI failed ({e}), trying Gemini...")
            if GOOGLE_API_KEY:
                try:
                    return _call_llm_gemini(prompt)
                except Exception as e2:
                    print(f"[WARNING] Gemini also failed ({e2}), using heuristics")
                    return ""
            return ""
    
    elif LLM_PROVIDER == "gemini":
        try:
            return _call_llm_gemini(prompt)
        except Exception as e:
            print(f"[WARNING] Gemini failed ({e}), trying OpenAI...")
            if OPENAI_API_KEY:
                try:
                    return _call_llm_openai(prompt)
                except Exception as e2:
                    print(f"[WARNING] OpenAI also failed ({e2}), using heuristics")
                    return ""
            return ""
    
    elif LLM_PROVIDER == "anthropic":
        try:
            return _call_llm_anthropic(prompt)
        except Exception as e:
            print(f"[WARNING] Anthropic failed ({e}), using heuristics")
            return ""
    
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
    """Parse LLM output into (type, text) tuples."""
    out: List[Tuple[ItemType, str]] = []
    if not raw:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        
        # Check for explicit tag
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
    Enrich items with K/A from LLM or heuristics.
    
    Returns only NEW items; caller should extend and dedupe.
    """
    # If disabled, use heuristics
    if LLM_PROVIDER in {"", "disabled", "off", "false", "0"}:
        print(f"[LLM] Provider disabled, using heuristics for {afsc_code}")
        return _heuristic_enhance(afsc_text, items)
    
    prompt = _PROMPT.format(
        afsc_text=afsc_text.strip()[:2000],
        existing=_format_existing(items),
    )
    
    try:
        print(f"[LLM] Calling {LLM_PROVIDER} for {afsc_code}...")
        raw = _provider_call(prompt)
        
        if not raw:
            print(f"[LLM] No response, using heuristics for {afsc_code}")
            return _heuristic_enhance(afsc_text, items)
        
        parsed = _parse_llm_lines(raw)
        new_items = []
        
        for item_type, text in parsed[:max_new]:
            new_items.append(ItemDraft(
                text=text,
                item_type=item_type,
                confidence=0.70,
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
    
    print(f"\nGenerated {len(new_items)} new items:")
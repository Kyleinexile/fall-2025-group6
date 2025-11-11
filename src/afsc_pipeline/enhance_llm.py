# src/afsc_pipeline/enhance_llm.py
"""
LLM-based enhancement for K/A (Knowledge / Ability) items with graceful fallbacks.
"""

from __future__ import annotations

import os
import re
import logging
from typing import List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType

# -------------------------
# Logging Setup
# -------------------------
logger = logging.getLogger(__name__)

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
    collos = re.findall(
        rf"\b({_word}\s+(analysis|intelligence|security|threats|operations|collection|targeting|briefing|reporting))\b",
        text,
        flags=re.IGNORECASE,
    )
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

    logger.info(f"Generated {len(new_items)} items via heuristics")
    return new_items

# -------------------------
# LLM Implementations
# -------------------------
def _call_llm_gemini(
    prompt: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 512,
    model: str | None = None
) -> str:
    """Call Google Gemini API with permissive safety and generation config."""
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set")
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=GOOGLE_API_KEY)
        mdl = model or LLM_MODEL_GEMINI
        model_obj = genai.GenerativeModel(mdl)

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        generation_config = {
            "temperature": float(temperature),
            "max_output_tokens": int(max_tokens),
        }

        resp = model_obj.generate_content(
            prompt,
            safety_settings=safety_settings,
            generation_config=generation_config,
        )
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            # Some SDK versions return candidates/parts instead of .text
            cands = getattr(resp, "candidates", None)
            if cands and getattr(cands[0], "content", None):
                parts = getattr(cands[0].content, "parts", None) or []
                text = "".join(getattr(p, "text", "") or "" for p in parts).strip()
        return text
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
            messages=[{"role": "user", "content": prompt}],
        )
        # message.content is a list of content blocks
        text_parts = []
        for block in getattr(message, "content", []) or []:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        return "\n".join(text_parts).strip()
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
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
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
            logger.warning(f"OpenAI failed: {e}, trying Gemini...")
            if GOOGLE_API_KEY:
                try:
                    return _call_llm_gemini(prompt)
                except Exception as e2:
                    logger.warning(f"Gemini also failed: {e2}, using heuristics")
                    return ""
            return ""
    elif LLM_PROVIDER == "gemini":
        try:
            return _call_llm_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini failed: {e}, trying OpenAI...")
            if OPENAI_API_KEY:
                try:
                    return _call_llm_openai(prompt)
                except Exception as e2:
                    logger.warning(f"OpenAI also failed: {e2}, using heuristics")
                    return ""
            return ""
    elif LLM_PROVIDER == "anthropic":
        try:
            return _call_llm_anthropic(prompt)
        except Exception as e:
            logger.warning(f"Anthropic failed: {e}, using heuristics")
            return ""
    return ""

# ---- Runtime override helpers (useful for Streamlit BYO-key page) -----------
def set_runtime_credentials(provider: str | None = None, api_key: str | None = None):
    """
    Override the provider and corresponding API key at runtime.
    This is optional, but convenient for a Streamlit 'Try it yourself' tab.
    """
    global LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
    if provider:
        LLM_PROVIDER = provider.strip().lower()
        logger.info(f"Runtime provider set to: {LLM_PROVIDER}")
    if api_key:
        if LLM_PROVIDER == "openai":
            OPENAI_API_KEY = api_key
            logger.debug("Runtime OpenAI API key configured")
        elif LLM_PROVIDER == "anthropic":
            ANTHROPIC_API_KEY = api_key
            logger.debug("Runtime Anthropic API key configured")
        elif LLM_PROVIDER in {"gemini", "google", "googleai"}:
            GOOGLE_API_KEY = api_key
            logger.debug("Runtime Gemini API key configured")

def run_llm(
    *,
    prompt: str,
    provider: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
    model: str | None = None,
) -> str:
    """
    Public, minimal LLM caller for ad-hoc prompts (e.g., 'Try it yourself' page).

    - If provider/api_key are given, they take precedence over module defaults.
    - Returns the raw text response (no parsing/sanitization).
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return ""

    prov = (provider or LLM_PROVIDER or "openai").strip().lower()
    logger.info(f"Running LLM with provider: {prov}")

    if prov == "openai":
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            mdl = model or LLM_MODEL_OPENAI
            resp = client.chat.completions.create(
                model=mdl,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except ImportError:
            raise ImportError("openai not installed")

    elif prov == "anthropic":
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            mdl = model or LLM_MODEL_ANTHROPIC
            msg = client.messages.create(
                model=mdl,
                max_tokens=max_tokens or 1024,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = []
            for block in getattr(msg, "content", []) or []:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
            return "\n".join(parts).strip()
        except ImportError:
            raise ImportError("anthropic not installed")

    elif prov in {"gemini", "google", "googleai"}:
        key = api_key or GOOGLE_API_KEY
        if not key:
            raise ValueError("GOOGLE_API_KEY not set")
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            return _call_llm_gemini(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except ImportError:
            raise ImportError("google-generativeai not installed")

    else:
        raise ValueError(f"Unsupported provider: {prov}")

# -------------------------
# Prompt + parse
# -------------------------
# NOTE: includes {missing_hint} which can be empty string
_PROMPT = """
You are assisting with extracting new Knowledge and Ability statements from an Air Force specialty description.

Return ONLY bullet lines — no explanations or prose.
Each line must start with a dash (-) and be at most 120 characters.
Write 3–6 new items that complement the existing ones and fill Knowledge/Ability gaps.
Use EXACT surface forms: "Knowledge of …" or "Ability to …".
Avoid duplicates (including paraphrases) of EXISTING ITEMS.
Ignore any leading tags like "[Knowledge]" or "[Ability]" in EXISTING ITEMS when checking duplicates.
Be specific and concrete; avoid vague generalities. No numbering; no trailing punctuation.
{missing_hint}

AFSC TEXT:
\"\"\"{afsc_text}\"\"\"

EXISTING ITEMS:
{existing}

FORMAT EXAMPLE:
- Knowledge of intelligence cycle fundamentals
- Ability to synthesize multi-source findings under time constraints
- Knowledge of geospatial analysis techniques
""".strip()

def _format_existing(items: List[ItemDraft]) -> str:
    """Render existing items as [- [Knowledge]/[Ability]] to guide the model."""
    if not items:
        return "- (none)"
    lines = []
    for it in items:
        # normalize to exactly two tags
        t = str(getattr(it, "item_type", "") or "").strip().lower()
        if hasattr(it, "item_type") and hasattr(it.item_type, "value"):
            t = str(it.item_type.value).strip().lower()
        tag = "Knowledge" if t.startswith("k") else "Ability" if t.startswith("a") else t.title() or "Item"
        text = str(getattr(it, "text", "")).strip()
        if text:
            lines.append(f"- [{tag}] {text}")
    return "\n".join(lines) if lines else "- (none)"

# ---- Output sanitization & duplicate guard ---------------------------------

# Accept only these stems
_BULLET_RE = re.compile(r"^\s*-\s*(Knowledge of|Ability to)\s.+$", re.IGNORECASE)

def _sanitize_lines(raw: str, max_len: int = 120) -> List[str]:
    """
    Filters model output to:
      - bullets only, starting with '- '
      - surface forms 'Knowledge of ...' or 'Ability to ...'
      - no trailing punctuation ; : , . ! ?
      - length <= max_len (excluding the leading '- ')
    Canonicalizes capitalization of the stems, and dedups exact matches.
    """
    if not raw:
        return []
    out: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if not _BULLET_RE.match(line):
            continue
        # Trim trailing punctuation
        line = re.sub(r"\s*[\.;:,!?]\s*$", "", line)
        # Canonicalize stems
        line = re.sub(r"^\s*-\s*knowledge of", "- Knowledge of", line, flags=re.IGNORECASE)
        line = re.sub(r"^\s*-\s*ability to", "- Ability to", line, flags=re.IGNORECASE)
        # Enforce logical length (without "- ")
        logical_len = len(line.lstrip()[2:].lstrip()) if line.lstrip().startswith("- ") else len(line)
        if logical_len <= max_len:
            out.append(line)
    # Deduplicate (case-insensitive)
    seen = set()
    deduped = []
    for l in out:
        key = l.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(l)
    return deduped

def _normalize_item_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"^\-\s*\[(knowledge|ability)\]\s*", "", s)   # strip tags from EXISTING
    s = re.sub(r"^\-\s*(knowledge of|ability to)\s*", "", s) # strip stems from new lines
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _filter_against_existing(generated: List[str], existing_block: str) -> List[str]:
    """Remove near-duplicates vs existing with simple normalization + substring checks."""
    existing_norm = []
    for line in existing_block.splitlines():
        line = line.strip()
        if line and line.startswith("-"):
            existing_norm.append(_normalize_item_text(line))
    keep: List[str] = []
    for g in generated:
        norm = _normalize_item_text(g)
        is_dup = any(norm == e or norm in e or e in norm for e in existing_norm)
        if not is_dup:
            keep.append(g)
    return keep

def _parse_llm_lines(raw: str) -> List[Tuple[ItemType, str]]:
    """
    Parse LLM output into (type, text) tuples.
    Accepts only Knowledge/Ability (never Skill).
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

        # Tag form: [Knowledge] / [Ability]
        m = re.match(r"\[(knowledge|ability)\]\s+(.*)$", line, re.IGNORECASE)
        if m:
            tag = m.group(1).lower()
            txt = m.group(2).strip()
            txt = re.sub(r"\s*[\.;:,!?]\s*$", "", txt)
            if tag.startswith("k"):
                out.append((ItemType.KNOWLEDGE, txt))
            elif tag.startswith("a"):
                out.append((ItemType.ABILITY, txt))
            continue

        # Surface form
        txt = re.sub(r"\s*[\.;:,!?]\s*$", "", line)
        low = txt.lower()
        if low.startswith("knowledge of "):
            out.append((ItemType.KNOWLEDGE, txt))
        elif low.startswith("ability to "):
            out.append((ItemType.ABILITY, txt))
        else:
            continue
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
        logger.info(f"LLM provider disabled, using heuristics for {afsc_code}")
        return _heuristic_enhance(afsc_text, items)

    # Count existing items by type to create a balancing hint
    k_count = sum(1 for it in items if it.item_type == ItemType.KNOWLEDGE)
    a_count = sum(1 for it in items if it.item_type == ItemType.ABILITY)

    if k_count == 0 and a_count == 0:
        missing_hint = "Generate a balanced mix of Knowledge and Ability items."
    elif k_count == 0:
        missing_hint = "Currently heavy on Abilities; prefer 3–4 Knowledge items."
    elif a_count == 0:
        missing_hint = "Currently heavy on Knowledge; prefer 3–4 Ability items."
    elif k_count < 2:
        missing_hint = "Prefer more Knowledge items to balance coverage."
    elif a_count < 2:
        missing_hint = "Prefer more Ability items to balance coverage."
    else:
        missing_hint = "Balance Knowledge and Ability items."

    existing_formatted = _format_existing(items)
    prompt = _PROMPT.format(
        afsc_text=afsc_text.strip()[:2000],  # token safety
        existing=existing_formatted,
        missing_hint=missing_hint,
    )

    try:
        logger.info(f"Calling {LLM_PROVIDER} for {afsc_code}...")
        raw = _provider_call(prompt)

        if not raw:
            logger.warning(f"No LLM response for {afsc_code}, using heuristics")
            return _heuristic_enhance(afsc_text, items)

        # Sanitize and filter against existing
        clean_lines = _sanitize_lines(raw)
        clean_lines = _filter_against_existing(clean_lines, existing_formatted)

        # Convert to ItemDrafts
        parsed = _parse_llm_lines("\n".join(clean_lines))
        new_items: List[ItemDraft] = []
        for item_type, text in parsed[:max_new]:
            new_items.append(ItemDraft(
                text=text,
                item_type=item_type,
                confidence=0.70,
                source=f"llm-{LLM_PROVIDER}",
                esco_id=None,
            ))

        logger.info(f"Generated {len(new_items)} new items for {afsc_code} via {LLM_PROVIDER}")
        return new_items

    except Exception as e:
        logger.error(f"LLM error for {afsc_code}: {e}", exc_info=True)
        logger.info("Falling back to heuristics")
        return _heuristic_enhance(afsc_text, items)

# -------------------------
# Test function
# -------------------------
if __name__ == "__main__":
    # Configure logging for test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    sample_text = """
    Performs and manages intelligence targeting operations and training.
    Performs intelligence data analysis. Determines intelligence
    information requirements. Analyzes data from multiple sources.
    Identifies targets. Prepares intelligence assessments and reports.
    """
    sample_items = [
        ItemDraft(
            text="intelligence data analysis",
            item_type=ItemType.SKILL,
            confidence=0.65,
            source="laiser",
            esco_id="ESCO.1234",
        ),
        ItemDraft(
            text="prepare intelligence reports",
            item_type=ItemType.SKILL,
            confidence=0.58,
            source="laiser",
            esco_id=None,
        ),
    ]
    logger.info("=" * 60)
    logger.info("Testing LLM Enhancement")
    logger.info("=" * 60)
    logger.info(f"Provider: {LLM_PROVIDER}")
    logger.info(f"Existing items: {len(sample_items)}")
    
    new_items = enhance_items_with_llm(
        afsc_code="1N0X1",
        afsc_text=sample_text,
        items=sample_items,
    )
    
    logger.info(f"Generated {len(new_items)} new items:")
    for ni in new_items:
        logger.info(f"- {ni.item_type.value}: {ni.text}")
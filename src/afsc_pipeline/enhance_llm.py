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
LLM_PROVIDER=gemini|openai|anthropic|disabled   (default: disabled)
LLM_MODEL_GEMINI=gemini-1.5-pro                 (example)
LLM_MODEL_OPENAI=gpt-4o-mini                    (example)
LLM_MODEL_ANTHROPIC=claude-3-5-sonnet-20241022  (example)

# Keys (only if you actually wire an SDK or HTTP call in your project):
GOOGLE_API_KEY=<key>
OPENAI_API_KEY=<key>
ANTHROPIC_API_KEY=<key>

Notes
-----
- This file ships WITHOUT external SDK calls for portability.
- The call sites are stubbed; you can drop in your preferred client code.
- Output type is ItemDraft (same as extractor) to keep graph_writer idempotent.
"""

from __future__ import annotations

import os
import re
import hashlib
from typing import Iterable, List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType


# -------------------------
# Config
# -------------------------
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "disabled").strip().lower()
LLM_MODEL_GEMINI = os.getenv("LLM_MODEL_GEMINI", "gemini-1.5-pro")
LLM_MODEL_OPENAI = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")
LLM_MODEL_ANTHROPIC = os.getenv("LLM_MODEL_ANTHROPIC", "claude-3-5-sonnet-20241022")


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
    have_k = any(it.item_type == ItemType.knowledge for it in items)
    have_a = any(it.item_type == ItemType.ability for it in items)

    new_items: List[ItemDraft] = []

    # Ability from existing skills
    if not have_a:
        # find 1-2 good verbs from existing skills
        verbs = []
        for it in items:
            if it.item_type != ItemType.skill:
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
                item_type=ItemType.ability,
                confidence=0.55,
                source="llm-heuristic",
                esco_id=None,
                content_sig=_sig(text, ItemType.ability, tag="llm-heuristic-v1"),
            ))

    # Knowledge from topical candidates
    if not have_k:
        topics = _topical_candidates(afsc_text, max_items=3)
        for t in topics:
            text = f"Knowledge of {t}"
            new_items.append(ItemDraft(
                text=text,
                item_type=ItemType.knowledge,
                confidence=0.55,
                source="llm-heuristic",
                esco_id=None,
                content_sig=_sig(text, ItemType.knowledge, tag="llm-heuristic-v1"),
            ))

    return new_items


# -------------------------
# LLM call stubs (replace with your SDK of choice, if desired)
# -------------------------
def _call_llm_gemini(prompt: str) -> str:
    """
    Stub. Replace with google.generativeai or HTTP call in your project.
    Return a plain text list of bullet lines to parse into items.
    """
    raise NotImplementedError("Gemini call not wired. Set LLM_PROVIDER=disabled to use heuristics.")

def _call_llm_openai(prompt: str) -> str:
    """Stub for OpenAI."""
    raise NotImplementedError("OpenAI call not wired. Set LLM_PROVIDER=disabled to use heuristics.")

def _call_llm_anthropic(prompt: str) -> str:
    """Stub for Anthropic."""
    raise NotImplementedError("Anthropic call not wired. Set LLM_PROVIDER=disabled to use heuristics.")


def _provider_call(prompt: str) -> str:
    if LLM_PROVIDER == "gemini":
        return _call_llm_gemini(prompt)
    if LLM_PROVIDER == "openai":
        return _call_llm_openai(prompt)
    if LLM_PROVIDER == "anthropic":
        return _call_llm_anthropic(prompt)
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
"""

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
            t = ItemType(m.group(1).lower())
            text = m.group(2).strip().rstrip(".")
        else:
            txt = line.rstrip(".")
            low = txt.lower()
            if low.startswith("knowledge of "):
                t = ItemType.knowledge
                text = txt
            elif low.startswith("ability to "):
                t = ItemType.ability
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
    """
    # If provider disabled, do heuristic only
    if LLM_PROVIDER in {"", "disabled", "off", "false", "0"}:
        return _heuristic_enhance(afsc_text, items)

    prompt = _PROMPT.format(
        afsc_text=afsc_text.strip(),
        existing=_format_existing(items),
    )

    try:
        raw = _provider_call(prompt)
    except NotImplementedError:
        # Provider not wired; safe fallb

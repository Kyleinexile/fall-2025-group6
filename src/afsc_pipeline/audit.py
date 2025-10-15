# src/afsc_pipeline/audit.py
from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List


def _now_ms() -> int:
    return int(time.time() * 1000)


def _json_print(record: Dict[str, Any]) -> None:
    """
    Emit a single JSON line to stdout. Safe for Streamlit/CLI logs.
    """
    try:
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception:
        # Fall back to a plain print if JSON or IO fails
        print(record)


def log_extract_event(
    *,
    afsc_code: str,
    used_fallback: bool,
    errors: List[str],
    duration_ms: int,
    n_items: int,
    write_stats: Dict[str, int],
) -> None:
    """
    Structured, side-effect-free audit logging for one pipeline run.

    Parameters
    ----------
    afsc_code : str
        AFSC identifier (e.g., '1N0X1').
    used_fallback : bool
        True if LAiSER failed/was disabled and heuristics were used.
    errors : List[str]
        Any extraction-stage error codes/messages (e.g., 'laiser_error:Timeout').
    duration_ms : int
        Extraction stage duration from the extractor result.
    n_items : int
        Number of items actually written after dedupe/filters.
    write_stats : Dict[str, int]
        Neo4j summary counters returned by graph_writer.upsert_afsc_and_items.
    """
    record = {
        "ts_ms": _now_ms(),
        "event": "pipeline_extract",
        "afsc_code": afsc_code,
        "used_fallback": used_fallback,
        "errors": errors or [],
        "duration_ms": int(duration_ms),
        "n_items_written": int(n_items),
        "write_stats": write_stats or {},
    }
    _json_print(record)

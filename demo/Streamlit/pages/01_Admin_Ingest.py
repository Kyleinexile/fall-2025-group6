from __future__ import annotations

# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib, os, json, time, re
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root (…/fall-2025-group6)
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

from typing import Dict, Any, List, Tuple

import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# --- Import your pipeline pieces ---
from afsc_pipeline.preprocess import clean_afsc_text  # noqa: F401
from afsc_pipeline.pipeline import run_pipeline, ItemDraft, ItemType  # noqa: F401

# ----------------------------
# Env / Config
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# LAiSER echo (read-only; pipeline still controls behavior via env)
USE_LAISER = os.getenv("USE_LAISER", "")
LAISER_MODE = os.getenv("LAISER_MODE", "")
LAISER_MODEL_ID = os.getenv("LAISER_MODEL_ID", "")
LAISER_ALIGN_TOPK = os.getenv("LAISER_ALIGN_TOPK", "")

# Optional gate (simple): set ADMIN_KEY in your Streamlit secrets or env.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

APP_TITLE = "Admin: AFSC Ingest (Run Pipeline → Aura → Viewer)"

# ----------------------------
# Helpers
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_driver():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError("Neo4j env vars are not fully set.")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # probe connection
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1 AS ok").single()
    except (ServiceUnavailable, AuthError) as e:
        raise RuntimeError(f"Neo4j connection failed: {e}") from e
    return driver


def summarize_items(items: List[ItemDraft]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["text", "item_type", "confidence", "source", "esco_id", "content_sig"])
    rows = []
    for it in items:
        rows.append({
            "text": it.text,
            "item_type": it.item_type.value if hasattr(it.item_type, "value") else str(it.item_type),
            "confidence": float(getattr(it, "confidence", 0.0) or 0.0),
            "source": getattr(it, "source", "") or "",
            "esco_id": getattr(it, "esco_id", "") or "",
            "content_sig": getattr(it, "content_sig", ""),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["confidence", "text"], ascending=[False, True]).reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=10)
def afsc_live_counts(code: str) -> Tuple[int, int]:
    """Return (HAS_ITEM count, REQUIRES count) for quick health checks."""
    with get_driver().session(database=NEO4J_DATABASE) as s:
        has = s.run("MATCH (:AFSC {code:$c})-[:HAS_ITEM]->(:Item) RETURN count(*) AS n", {"c": code}).single()["n"]
        req = s.run("MATCH (:AFSC {code:$c})-[:REQUIRES]->(:Item) RETURN count(*) AS n", {"c": code}).single()["n"]
    return int(has), int(req)


def looks_like_afsc(code: str) -> bool:
    # Flexible but safe enough for demo (1–2 digits + 1 letter + up to 2 alnums + 1–2 trailing [digit|X])
    return bool(re.fullmatch(r"[0-9]{1,2}[A-Z][A-Z0-9]{0,2}[0-9X]{1,2}", code.strip().upper()))


# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")
st.title(APP_TITLE)
st.caption("Paste AFSC text → Run pipeline → Write to Aura → Verify in the viewer page")

with st.expander("Connection & Settings", expanded=False):
    st.code(
        f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}\n"
        f"USE_LAISER={USE_LAISER}\nLAISER_MODE={LAISER_MODE}\n"
        f"LAISER_MODEL_ID={LAISER_MODEL_ID}\nLAISER_ALIGN_TOPK={LAISER_ALIGN_TOPK}",
        language="bash"
    )

# Optional admin key check
if ADMIN_KEY:
    entered = st.text_input(
        "Admin key",
        type="password",
        placeholder="Required to run",
        help="Set ADMIN_KEY in environment or Streamlit Secrets.",
    )
    if entered.strip() != ADMIN_KEY.strip():
        st.info("Enter the admin key to enable ingestion.")
        st.stop()

# =========================
# Single-AFSC ingest
# =========================
st.subheader("Single AFSC ingest")

col1, col2 = st.columns([1, 3], gap="large")
with col1:
    # Prefill AFSC code if present in session
    default_code = st.session_state.pop("admin_ingest_code", "1N1X1")
    afsc_code = st.text_input("AFSC code", value=default_code, help="Example: 1N1X1")

    clean_first = st.checkbox("Clean text before ingest", value=True,
                              help="Run light cleanup on punctuation, headers/footers, spacing.")
    min_conf = st.slider("Min confidence (post-filter view only)", 0.0, 1.0, 0.0, 0.05,
                         help="Display-only filter; pipeline still writes all extracted items.")

    st.markdown("**LAiSER settings (env-driven)**")
    st.caption("USE_LAISER=true, LAISER_MODE=lib (CPU align fallback), LAISER_ALIGN_TOPK=25 recommended.")
    run_btn = st.button("🚀 Run pipeline", type="primary", use_container_width=True)

with col2:
    # Prefill textarea if “Send to Admin Ingest” was used in Docs Viewer
    prefill = st.session_state.pop("admin_ingest_text", "")
    afsc_text = st.text_area(
        "AFSC text",
        height=320,
        value=prefill or "",
        placeholder="Paste the AFSC (Duties / Knowledge / Skills / Abilities) text here…",
    )

# Quick health (optional)
with st.expander("Quick health for this AFSC", expanded=False):
    if afsc_code.strip() and looks_like_afsc(afsc_code):
        try:
            has_n, req_n = afsc_live_counts(afsc_code.strip())
            st.write(f"Current Aura counts for **{afsc_code}** → HAS_ITEM: **{has_n}**, REQUIRES: **{req_n}**")
        except Exception as e:
            st.warning(f"Could not read counts: {e}")
    else:
        st.caption("Enter a valid AFSC code to see live counts.")

if run_btn:
    code = afsc_code.strip().upper()
    if not code or not afsc_text.strip():
        st.error("AFSC code and AFSC text are required.")
        st.stop()
    if not looks_like_afsc(code):
        st.warning("AFSC code format looks unusual. Proceeding anyway.")

    raw_text = afsc_text
    if clean_first:
        try:
            raw_text = clean_afsc_text(raw_text)
        except Exception:
            # Fail open—cleanup is convenience
            pass

    st.info("Starting pipeline…")
    with st.spinner("Extracting & writing to Neo4j…"):
        try:
            driver = get_driver()
            with driver.session(database=NEO4J_DATABASE) as session:
                summary: Dict[str, Any] = run_pipeline(
                    afsc_code=code,
                    afsc_raw_text=raw_text,
                    neo4j_session=session,
                )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # Show results
    st.success("Ingest complete.")
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Items (raw)", summary.get("n_items_raw", 0))
    colB.metric("After filters", summary.get("n_items_after_filters", 0))
    colC.metric("After dedupe", summary.get("n_items_after_dedupe", 0))
    colD.metric("Used fallback?", "Yes" if summary.get("used_fallback") else "No")

    # Items preview (from pipeline output if present; else query Aura)
    df_preview = pd.DataFrame()
    items_written = summary.get("items")
    if items_written and isinstance(items_written, list):
        df_preview = summarize_items(items_written)
    else:
        try:
            with driver.session(database=NEO4J_DATABASE) as s:
                rows = list(s.run("""
                    MATCH (a:AFSC {code: $code})-[:HAS_ITEM|:REQUIRES]->(i)
                    RETURN i.text AS text, i.item_type AS item_type,
                           coalesce(i.confidence,0.0) AS confidence,
                           coalesce(i.source,'') AS source,
                           coalesce(i.esco_id,'') AS esco_id,
                           coalesce(i.content_sig,'') AS content_sig
                    ORDER BY confidence DESC, text ASC
                """, {"code": code}))
            df_preview = pd.DataFrame(rows)
        except Exception as e:
            st.warning(f"Could not fetch items for preview: {e}")

    if not df_preview.empty and min_conf > 0:
        df_preview = df_preview[df_preview["confidence"] >= float(min_conf)].reset_index(drop=True)

    st.subheader("Preview of items")
    if df_preview.empty:
        st.info("No items found to display (try a different AFSC excerpt).")
    else:
        st.dataframe(df_preview.head(50), use_container_width=True, hide_index=True)
        st.caption("Showing up to 50 rows.")

    # Live counts after write
    try:
        has_n, req_n = afsc_live_counts(code)
        st.caption(f"Post-ingest Aura counts for **{code}** → HAS_ITEM: **{has_n}**, REQUIRES: **{req_n}**")
    except Exception:
        pass

    st.markdown("---")
    st.caption("Open the main viewer page to see these items with filters/CSV (Simple App tab).")

# =========================
# Bulk JSONL ingest (Claude output)
# =========================
st.subheader("Bulk JSONL ingest")
st.caption("Upload a JSONL with one AFSC per line (fields like: afsc, md, sections, source). Each line will be run through the same pipeline.")

jsonl_file = st.file_uploader("Upload JSONL (one AFSC per line)", type=["jsonl"])
if jsonl_file is not None:
    if st.button("🚀 Ingest JSONL", use_container_width=True):
        try:
            driver = get_driver()
        except Exception as e:
            st.error(f"Neo4j connection error: {e}")
            st.stop()

        lines = jsonl_file.getvalue().decode("utf-8", errors="replace").splitlines()
        total = len(lines)
        ok = fail = 0
        pb = st.progress(0)
        log = st.empty()

        with driver.session(database=NEO4J_DATABASE) as session:
            for i, line in enumerate(lines, start=1):
                try:
                    if not line.strip():
                        fail += 1
                    else:
                        obj = json.loads(line)
                        code = (obj.get("afsc") or "").strip().upper()
                        text_body = obj.get("md") or json.dumps(obj.get("sections", {}), ensure_ascii=False)
                        if not code or not text_body:
                            fail += 1
                        else:
                            # Optional cleaning for bulk too
                            try:
                                text_body = clean_afsc_text(text_body)
                            except Exception:
                                pass
                            run_pipeline(
                                afsc_code=code,
                                afsc_raw_text=text_body,
                                neo4j_session=session,
                            )
                            ok += 1
                except Exception:
                    fail += 1
                pb.progress(min(i / max(total, 1), 1.0))
                log.text(f"Ingested {i}/{total} … success={ok}, fail={fail}")
                time.sleep(0.01)

        st.success(f"Bulk ingest complete — success: {ok}, failed: {fail}. Open the viewer tab to verify.")

# =========================
# Danger Zone (delete)
# =========================
with st.expander("Danger zone: delete AFSCs + their items", expanded=False):
    st.warning("This permanently deletes selected AFSC nodes and any now-orphaned Item nodes.", icon="⚠️")
    codes_text = st.text_area(
        "AFSC codes (comma/space/newline separated)",
        placeholder="e.g. 1N1X1, 17S3X, 1D7"
    )
    confirm = st.checkbox("I understand this will permanently delete data.")
    if st.button("🧨 Delete selected AFSCs", disabled=not confirm):
        try:
            codes = [c.strip().upper() for c in re.split(r"[,\s]+", codes_text or "") if c.strip()]
            codes = sorted(set(codes))
            if not codes:
                st.error("Enter at least one AFSC code.")
            else:
                with get_driver().session(database=NEO4J_DATABASE) as s:
                    # count before
                    pre = s.run("MATCH (a:AFSC) WHERE a.code IN $codes RETURN count(a) AS n", {"codes": codes}).single()["n"]

                    # 1) Remove AFSC→Item rels and delete Items that become orphaned
                    q1 = """
                    MATCH (a:AFSC)
                    WHERE a.code IN $codes
                    OPTIONAL MATCH (a)-[r:HAS_ITEM|REQUIRES]->(i:Item)
                    DELETE r
                    WITH DISTINCT i
                    WHERE i IS NOT NULL AND NOT ( ()-[:HAS_ITEM|REQUIRES]->(i) )
                    DELETE i
                    """
                    s.run(q1, {"codes": codes})

                    # 2) Delete the AFSC nodes themselves
                    q2 = """
                    MATCH (a:AFSC)
                    WHERE a.code IN $codes
                    DETACH DELETE a
                    """
                    s.run(q2, {"codes": codes})

                    # count after
                    post = s.run("MATCH (a:AFSC) WHERE a.code IN $codes RETURN count(a) AS n", {"codes": codes}).single()["n"]

                removed = pre - post
                st.success(f"Deleted AFSCs: {', '.join(codes)}  •  Removed {removed} AFSC node(s).")
        except Exception as e:
            st.error(f"Delete failed: {e}")

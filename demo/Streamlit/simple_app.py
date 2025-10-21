# demo/Streamlit/pages/01_Admin_Ingest.py
from __future__ import annotations

# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib, os, json, time, re
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # .../fall-2025-group6
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

from typing import Dict, Any, List

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

# Optional gate (simple): set ADMIN_KEY in env or Streamlit secrets.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

APP_TITLE = "Admin: AFSC Ingest (Run Pipeline → Aura → Viewer)"

# Where pre-split AFSC markdowns live (from pdf_to_afsc_text.py tool)
DOCS_ROOT = pathlib.Path("/workspaces/docs_text")
DOC_FOLDERS = [
    ("AFECD", DOCS_ROOT / "AFECD"),  # enlisted
    ("AFOCD", DOCS_ROOT / "AFOCD"),  # officer
]

# ----------------------------
# Helpers
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_driver():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError("Neo4j env vars are not fully set.")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
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


@st.cache_data(show_spinner=False, ttl=30)
def build_afsc_index() -> pd.DataFrame:
    """Build an index of pre-split AFSC markdowns. Safe when empty."""
    cols = ["afsc", "source", "path"]
    rows = []
    for source, folder in DOC_FOLDERS:
        if folder.exists():
            for p in folder.glob("*.md"):
                rows.append({"afsc": p.stem, "source": source, "path": str(p)})
    if not rows:
        return pd.DataFrame(columns=cols)
    return (
        pd.DataFrame(rows, columns=cols)
        .sort_values(["source", "afsc"])
        .reset_index(drop=True)
    )


# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")
st.title(APP_TITLE)
st.caption("Paste AFSC text → Run pipeline → Write to Aura → Verify in the viewer page")

with st.expander("Connection", expanded=False):
    st.code(f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}", language="bash")

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
# Quick browse: pre-split AFSC docs (optional helper)
# =========================
with st.expander("📂 Browse pre-split AFSC docs (optional helper)", expanded=False):
    df_idx = build_afsc_index()
    if df_idx.empty:
        st.info("No pre-split docs found yet.")
        with st.expander("Where we looked", expanded=False):
            st.write({
                "DOCS_ROOT": str(DOCS_ROOT),
                "folders": {src: str(path) for src, path in DOC_FOLDERS},
                "exists": {src: path.exists() for src, path in DOC_FOLDERS},
                "example_expected": "/workspaces/docs_text/AFECD/1N1X1.md",
            })
    else:
        colA, colB = st.columns([1, 3], gap="large")
        with colA:
            sources = ["All"] + sorted(df_idx["source"].unique().tolist())
            src_pick = st.selectbox("Source", options=sources, index=0)
            subset = df_idx if src_pick == "All" else df_idx[df_idx["source"] == src_pick]
            q = st.text_input("Filter by AFSC code (contains)", placeholder="e.g., 1N1, 11F")
            if q.strip():
                subset = subset[subset["afsc"].str.contains(q.strip(), case=False, na=False)]
            opt_labels = [f"{r.afsc} ({r.source})" for r in subset.itertuples()]
            which = st.selectbox("Pick AFSC", options=opt_labels if opt_labels else ["<none>"])
        with colB:
            if which and which != "<none>":
                afsc_code = which.split(" ", 1)[0]
                path = subset[subset["afsc"] == afsc_code]["path"].iloc[0]
                try:
                    text = pathlib.Path(path).read_text(encoding="utf-8")
                except Exception as e:
                    text = f"[Could not read file: {e}]"
                st.text_area("AFSC text (copy into the ingest form below if desired)", value=text, height=260)

# =========================
# Single-AFSC ingest
# =========================
st.subheader("Single AFSC ingest")

col1, col2 = st.columns([1, 3], gap="large")
with col1:
    afsc_code = st.text_input("AFSC code", value="1N1X1", help="Example: 1N1X1")
    # (Retained for future use; currently pipeline handles its own thresholds.)
    st.caption("LAiSER (env): USE_LAISER=true, LAISER_MODE=lib, LAISER_ALIGN_TOPK=25 recommended.")
    run_btn = st.button("🚀 Run pipeline", type="primary", use_container_width=True)

with col2:
    afsc_text = st.text_area(
        "AFSC text",
        height=300,
        placeholder="Paste the AFSC (Duties / Knowledge / Skills / Abilities) text here…",
    )

if run_btn:
    if not afsc_code.strip() or not afsc_text.strip():
        st.error("AFSC code and AFSC text are required.")
        st.stop()

    st.info("Starting pipeline…")
    with st.spinner("Extracting & writing to Neo4j…"):
        try:
            driver = get_driver()
            with driver.session(database=NEO4J_DATABASE) as session:
                summary: Dict[str, Any] = run_pipeline(
                    afsc_code=afsc_code.strip(),
                    afsc_raw_text=afsc_text,
                    neo4j_session=session,
                )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # Show results
    st.success("Done.")
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Items (raw)", summary.get("n_items_raw", 0))
    colB.metric("After filters", summary.get("n_items_after_filters", 0))
    colC.metric("After dedupe", summary.get("n_items_after_dedupe", 0))
    colD.metric("Used fallback?", "Yes" if summary.get("used_fallback") else "No")

    # Items preview (from pipeline output if present; else query Aura)
    items_written = summary.get("items")
    if items_written and isinstance(items_written, list):
        df = summarize_items(items_written)
        st.subheader("Preview of items (from pipeline output)")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.subheader("Preview of items (fresh from Aura)")
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
                """, {"code": afsc_code.strip()}))
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Could not fetch items for preview: {e}")

    st.markdown("---")
    st.caption("Switch to the main viewer tab to see these items with filters/CSV.")

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

        lines = jsonl_file.getvalue().decode("utf-8").splitlines()
        total = len(lines)
        ok = fail = 0
        pb = st.progress(0)
        log = st.empty()

        with driver.session(database=NEO4J_DATABASE) as session:
            for i, line in enumerate(lines, start=1):
                try:
                    obj = json.loads(line)
                    afsc_code = (obj.get("afsc") or "").strip()
                    # Prefer the Markdown body; fall back to structured sections
                    afsc_text = obj.get("md") or json.dumps(obj.get("sections", {}), ensure_ascii=False)
                    if not afsc_code or not afsc_text:
                        fail += 1
                    else:
                        run_pipeline(
                            afsc_code=afsc_code,
                            afsc_raw_text=afsc_text,
                            neo4j_session=session,
                        )
                        ok += 1
                except Exception:
                    fail += 1
                pb.progress(min(i / total, 1.0))
                log.text(f"Ingested {i}/{total} … success={ok}, fail={fail}")
                time.sleep(0.01)

        st.success(f"Bulk ingest complete — success: {ok}, failed: {fail}. Open the main tab to verify.")

# =========================
# Danger zone: delete AFSCs + their items
# =========================
with st.expander("🛑 Danger zone: delete AFSCs + their items", expanded=False):
    st.warning("This permanently deletes selected AFSC nodes and any now-orphaned Item nodes.")
    codes_text = st.text_area("AFSC codes (comma/space/newline separated)", placeholder="e.g. 1N1X1, 17S3X, 1D7")
    confirm = st.checkbox("I understand this will permanently delete data.")
    if st.button("🧨 Delete selected AFSCs", disabled=not confirm, use_container_width=True):
        try:
            codes = [c.strip() for c in re.split(r"[,\s]+", codes_text or "") if c.strip()]
            if not codes:
                st.error("Enter at least one AFSC code.")
            else:
                with get_driver().session(database=NEO4J_DATABASE) as s:
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

                st.success(f"Deleted AFSCs: {', '.join(codes)}")
                # Offer a quick page reload so the viewer reflects changes immediately
                if st.button("🔄 Reload page", use_container_width=True):
                    try:
                        st.rerun()
                    except Exception:
                        st.experimental_rerun()
        except Exception as e:
            st.error(f"Delete failed: {e}")

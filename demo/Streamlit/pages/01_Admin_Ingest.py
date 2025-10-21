# demo/Streamlit/pages/01_Admin_Ingest.py
from __future__ import annotations

# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib, os, json, time, re
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root (…/fall-2025-group6)
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# --- Your pipeline pieces ---
from afsc_pipeline.preprocess import clean_afsc_text  # import ensures module is reachable
from afsc_pipeline.pipeline import run_pipeline, ItemDraft

# ----------------------------
# Env / Config
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")  # optional guard

APP_TITLE = "Ingest AFSCs (Docs → Pipeline → Aura)"

# Where the pre-split AFSC markdowns live (produced by pdf_to_afsc_text.py)
DOCS_ROOT = pathlib.Path("/workspaces/docs_text")
DOC_FOLDERS = [("AFECD", DOCS_ROOT / "AFECD"), ("AFOCD", DOCS_ROOT / "AFOCD")]

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

@st.cache_data(show_spinner=False, ttl=30)
def build_afsc_index() -> pd.DataFrame:
    rows = []
    for source, folder in DOC_FOLDERS:
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            rows.append({"afsc": p.stem, "source": source, "path": str(p)})
    return pd.DataFrame(rows).sort_values(["source", "afsc"]).reset_index(drop=True)

def summarize_items(items: List[ItemDraft]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["text", "item_type", "confidence", "source", "esco_id", "content_sig"])
    rows = []
    for it in items:
        rows.append({
            "text": it.text,
            "item_type": getattr(it.item_type, "value", str(getattr(it, "item_type", ""))),
            "confidence": float(getattr(it, "confidence", 0.0) or 0.0),
            "source": getattr(it, "source", "") or "",
            "esco_id": getattr(it, "esco_id", "") or "",
            "content_sig": getattr(it, "content_sig", ""),
        })
    return pd.DataFrame(rows).sort_values(["confidence","text"], ascending=[False, True]).reset_index(drop=True)

def n_chars(s: Optional[str]) -> int:
    return len(s or "")

# ----------------------------
# UI: Header & guard
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")
st.title(APP_TITLE)
st.caption("Find your AFSC text → (optional) dry-run preview → run pipeline to write KSAs to Aura → verify in the Explore page.")

with st.expander("Connection", expanded=False):
    st.code(f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}", language="bash")

if ADMIN_KEY:
    entered = st.text_input("Admin key", type="password", placeholder="Required to run", help="Set ADMIN_KEY in environment or Streamlit Secrets.")
    if entered.strip() != ADMIN_KEY.strip():
        st.info("Enter the admin key to enable ingestion.")
        st.stop()

# ----------------------------
# 1) Left: Find AFSC text (from local docs)
# ----------------------------
left, right = st.columns([1.2, 2.0], gap="large")

with left:
    st.subheader("Find AFSC text")
    df_idx = build_afsc_index()
    if df_idx.empty:
        st.warning("No docs found under /workspaces/docs_text/{AFECD,AFOCD}. Use the PDF tool to generate them first.")
    else:
        q = st.text_input("Search AFSC code or source (regex or plain contains)", placeholder="e.g., 1N1X1 or (?i)^11")
        mode = st.radio("Match mode", ["Contains", "Regex"], horizontal=True)
        filtered = df_idx
        if q.strip():
            if mode == "Regex":
                try:
                    pat = re.compile(q)
                    mask = df_idx["afsc"].str.contains(pat) | df_idx["source"].str.contains(pat)
                    filtered = df_idx[mask]
                except re.error:
                    st.error("Invalid regex pattern.")
            else:
                s = q.strip().lower()
                mask = df_idx["afsc"].str.lower().str.contains(s) | df_idx["source"].str.lower().str.contains(s)
                filtered = df_idx[mask]

        st.caption(f"Found {len(filtered)} / {len(df_idx)}")
        pick = st.selectbox(
            "Select AFSC doc",
            options=[f"{r.afsc} ({r.source})" for r in filtered.itertuples()],
            index=0 if len(filtered) else None
        )

        preview_md = ""
        picked_code = ""
        if pick:
            picked_code = pick.split(" ", 1)[0]
            row = filtered[filtered["afsc"] == picked_code].iloc[0]
            try:
                preview_md = pathlib.Path(row["path"]).read_text(encoding="utf-8")
            except Exception as e:
                st.error(f"Could not read file: {e}")
                preview_md = ""

        st.text_area("Preview (read-only)", preview_md, height=260)

        if st.button("➡️ Use this text in ingest form", use_container_width=True, disabled=(not preview_md)):
            st.session_state["afsc_loaded_text"] = preview_md
            st.session_state["afsc_loaded_code"] = picked_code
            st.success("Loaded into the ingest form (right panel).")

# ----------------------------
# 2) Right: Ingest form (single AFSC)
# ----------------------------
with right:
    st.subheader("Single AFSC ingest")

    afsc_code = st.text_input(
        "AFSC code",
        value=st.session_state.get("afsc_loaded_code", "1N1X1"),
        help="Example: 1N1X1"
    )

    afsc_text = st.text_area(
        "AFSC text",
        height=260,
        value=st.session_state.get("afsc_loaded_text", ""),
        placeholder="Paste or load AFSC (Duties / Knowledge / Skills / Abilities) text here…",
    )

    colA, colB, colC = st.columns([1,1,1])
    with colA:
        if st.button("👀 Dry-run preview", use_container_width=True, disabled=(n_chars(afsc_text) == 0)):
            cleaned = clean_afsc_text(afsc_text or "")
            st.info(f"Characters: raw={n_chars(afsc_text)} • cleaned={n_chars(cleaned)}")
            with st.expander("Show cleaned text", expanded=False):
                st.text_area("Cleaned", cleaned, height=220)
    with colB:
        min_conf = st.slider("Min confidence (post-filter)", 0.0, 1.0, 0.0, 0.05)
    with colC:
        run_now = st.button("🚀 Run pipeline → Aura", type="primary", use_container_width=True, disabled=(n_chars(afsc_text) == 0 or n_chars(afsc_code) == 0))

    if run_now:
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
            else:
                st.success("Done.")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Items (raw)", summary.get("n_items_raw", 0))
                m2.metric("After filters", summary.get("n_items_after_filters", 0))
                m3.metric("After dedupe", summary.get("n_items_after_dedupe", 0))
                m4.metric("Used fallback?", "Yes" if summary.get("used_fallback") else "No")

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

    st.caption("Tip: After ingest, open **Explore KSAs** to see items with filtering & CSV export.")

st.divider()

# ----------------------------
# 3) Bulk JSONL ingest (Claude output / your JSONL)
# ----------------------------
st.subheader("Bulk JSONL ingest")
st.caption("Upload a JSONL file with one AFSC per line. Expected fields: `afsc` and either `md` (markdown body) or `sections`.")
jsonl_file = st.file_uploader("Upload JSONL (one AFSC per line)", type=["jsonl"])

if jsonl_file is not None:
    if st.button("🚀 Ingest JSONL", use_container_width=True):
        try:
            driver = get_driver()
        except Exception as e:
            st.error(f"Neo4j connection error: {e}")
        else:
            lines = jsonl_file.getvalue().decode("utf-8").splitlines()
            total = len(lines)
            ok = fail = 0
            pb = st.progress(0)
            log = st.empty()
            with driver.session(database=NEO4J_DATABASE) as session:
                for i, line in enumerate(lines, start=1):
                    try:
                        obj = json.loads(line)
                        code = (obj.get("afsc") or "").strip()
                        text = obj.get("md") or json.dumps(obj.get("sections", {}), ensure_ascii=False)
                        if not code or not text:
                            fail += 1
                        else:
                            run_pipeline(afsc_code=code, afsc_raw_text=text, neo4j_session=session)
                            ok += 1
                    except Exception:
                        fail += 1
                    pb.progress(min(i / total, 1.0))
                    log.text(f"Ingested {i}/{total} … success={ok}, fail={fail}")
                    time.sleep(0.01)
            st.success(f"Bulk ingest complete — success: {ok}, failed: {fail}. Open Explore to verify.")

st.divider()

# ----------------------------
# 4) Danger Zone: delete AFSCs + orphaned Items
# ----------------------------
with st.expander("Danger zone: delete AFSCs + their items", expanded=False):
    st.warning("This permanently deletes selected AFSC nodes and any now-orphaned Item nodes.")
    codes_text = st.text_area("AFSC codes (comma / space / newline separated)", placeholder="e.g. 1N1X1, 17S3X, 1D7")
    confirm_phrase = st.text_input("Type DELETE to confirm")
    delete_ok = (confirm_phrase.strip().upper() == "DELETE")
    if st.button("🧨 Delete selected AFSCs", disabled=not delete_ok, use_container_width=True):
        try:
            codes = [c.strip() for c in re.split(r"[,\s]+", codes_text or "") if c.strip()]
            if not codes:
                st.error("Enter at least one AFSC code.")
            else:
                with get_driver().session(database=NEO4J_DATABASE) as s:
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

                    q2 = """
                    MATCH (a:AFSC)
                    WHERE a.code IN $codes
                    DETACH DELETE a
                    """
                    s.run(q2, {"codes": codes})
                st.success(f"Deleted AFSCs: {', '.join(codes)}")
                st.info("Use the refresh button below to clear app caches.")
        except Exception as e:
            st.error(f"Delete failed: {e}")

# ----------------------------
# 5) Maintenance: refresh caches
# ----------------------------
st.markdown("### Maintenance")
if st.button("🔄 Refresh app caches (data + connections)"):
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Caches cleared. Use the sidebar to navigate or refresh your browser tab.")
    except Exception as e:
        st.error(f"Could not clear caches: {e}")

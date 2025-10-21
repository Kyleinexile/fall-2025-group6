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

# --- Import your pipeline pieces ---
from afsc_pipeline.pipeline import run_pipeline, ItemDraft  # noqa: F401

# ----------------------------
# Env / Config
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Optional gate (simple): set ADMIN_KEY in your Streamlit secrets or env.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

APP_TITLE = "Ingest & Manage"

# Local doc roots (created by your pdf_to_afsc_text script)
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

def clear_all_caches():
    """One-click cache clear on both pages."""
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception:
        pass

def connection_badge() -> str:
    try:
        _ = get_driver()
        return "<span style='background:#e8fff1;color:#05603a;border:1px solid #abefc6;padding:2px 8px;border-radius:999px;'>Aura • Connected</span>"
    except Exception:
        return "<span style='background:#fff1f1;color:#b42318;border:1px solid #fda29b;padding:2px 8px;border-radius:999px;'>Aura • Disconnected</span>"

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
    df = pd.DataFrame(rows)
    return df.sort_values(["confidence", "text"], ascending=[False, True]).reset_index(drop=True)

def read_afsc_markdown_from_local(code: str) -> Optional[str]:
    code = (code or "").strip()
    if not code:
        return None
    for label, folder in DOC_FOLDERS:
        p = folder / f"{code}.md"
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return None

def delete_afscs(codes: List[str]) -> int:
    if not codes:
        return 0
    with get_driver().session(database=NEO4J_DATABASE) as s:
        # Remove AFSC->Item rels & delete Items that become orphaned
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

        # Delete AFSC nodes
        q2 = """
        MATCH (a:AFSC)
        WHERE a.code IN $codes
        DETACH DELETE a
        """
        s.run(q2, {"codes": codes})
    return len(codes)

# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")
st.title("Ingest & Manage")
st.caption("Paste or load AFSC text → (optional) Dry-run → Write to Aura → Verify in Explore tab")
st.markdown(connection_badge(), unsafe_allow_html=True)

# Global refresh
cols_top = st.columns([1, 1, 5])
with cols_top[0]:
    if st.button("🔄 Refresh app data (clear caches)", use_container_width=True):
        clear_all_caches()
        st.success("Caches cleared.")
        st.rerun()
with cols_top[1]:
    if st.button("🧪 Test connection", use_container_width=True):
        try:
            _ = get_driver()
            st.success("Neo4j connection OK")
        except Exception as e:
            st.error(f"Neo4j connection failed: {e}")

with st.expander("Connection", expanded=False):
    st.code(f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}", language="bash")

# Optional admin key check
if ADMIN_KEY:
    entered = st.text_input("Admin key", type="password", placeholder="Required to run", help="Set ADMIN_KEY in environment or Streamlit Secrets.")
    if entered.strip() != ADMIN_KEY.strip():
        st.info("Enter the admin key to enable ingestion.")
        st.stop()

with st.expander("What happens?", expanded=False):
    st.markdown("""
1) **Load** AFSC text (paste or use *Load from docs*).
2) **Dry-run** (optional) to preview extracted items **without writing** to Aura.
3) **Run pipeline** to write to Aura, then check the *Explore KSAs* tab.
""")

# =========================
# Single-AFSC ingest
# =========================
st.subheader("Single AFSC ingest")

col1, col2 = st.columns([1, 3], gap="large")
with col1:
    afsc_code = st.text_input("AFSC code", value="1N1X1", help="Example: 1N1X1")
    dry_run = st.checkbox("Dry-run (no write)", value=False, help="Preview items without writing to Aura")
    st.caption("LAiSER env: USE_LAISER=true • LAISER_MODE=lib • LAISER_ALIGN_TOPK=25")
    # Small quick delete for the typed code
    st.markdown("---")
    st.caption("Quick delete")
    if st.button("🗑️ Delete this AFSC", use_container_width=True):
        if not afsc_code.strip():
            st.error("Enter an AFSC code.")
        else:
            n = delete_afscs([afsc_code.strip()])
            clear_all_caches()
            st.success(f"Deleted AFSC {afsc_code} (count={n}).")
            st.rerun()

    # Load from docs
    st.markdown("---")
    if st.button("📥 Load from docs", use_container_width=True, help="Loads /workspaces/docs_text/AFECD|AFOCD/<AFSC>.md into the text area"):
        txt = read_afsc_markdown_from_local(afsc_code)
        if txt:
            st.session_state["afsc_loaded_text"] = txt
            st.success("Loaded text from local docs.")
        else:
            st.warning("No matching local doc found for that AFSC.")

with col2:
    afsc_text = st.text_area(
        "AFSC text",
        height=330,
        placeholder="Paste the AFSC (Duties / Knowledge / Skills / Abilities) text here…",
        value=st.session_state.get("afsc_loaded_text", ""),
    )

# Action buttons
run_cols = st.columns([1, 1, 5])
with run_cols[0]:
    preview_btn = st.button("👀 Dry-run preview", disabled=not dry_run, use_container_width=True)
with run_cols[1]:
    run_btn = st.button("🚀 Run pipeline", type="primary", use_container_width=True)

def _render_items_table(items: List[ItemDraft], label: str):
    df = summarize_items(items)
    st.subheader(label)
    st.dataframe(df, use_container_width=True, hide_index=True)

if preview_btn:
    if not afsc_code.strip() or not afsc_text.strip():
        st.error("AFSC code and AFSC text are required.")
    else:
        st.info("Running dry-run (no write)…")
        try:
            # Call pipeline but don't write: pass neo4j_session=None to skip writing
            summary: Dict[str, Any] = run_pipeline(
                afsc_code=afsc_code.strip(),
                afsc_raw_text=afsc_text,
                neo4j_session=None,            # <— prevents writes
            )
            items = summary.get("items", [])
            _render_items_table(items, "Preview items (dry-run)")
            st.success("Dry-run complete. To save, turn off Dry-run and click 'Run pipeline'.")
        except Exception as e:
            st.error(f"Dry-run error: {e}")

if run_btn:
    if not afsc_code.strip() or not afsc_text.strip():
        st.error("AFSC code and AFSC text are required.")
    elif dry_run:
        st.warning("Dry-run is enabled. Disable it to write to Aura.")
    else:
        st.info("Starting pipeline…")
        with st.spinner("Extracting & writing to Neo4j…"):
            try:
                with get_driver().session(database=NEO4J_DATABASE) as session:
                    summary: Dict[str, Any] = run_pipeline(
                        afsc_code=afsc_code.strip(),
                        afsc_raw_text=afsc_text,
                        neo4j_session=session,
                    )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
            else:
                st.success("Done.")
                colA, colB, colC, colD = st.columns(4)
                colA.metric("Items (raw)", summary.get("n_items_raw", 0))
                colB.metric("After filters", summary.get("n_items_after_filters", 0))
                colC.metric("After dedupe", summary.get("n_items_after_dedupe", 0))
                colD.metric("Used fallback?", "Yes" if summary.get("used_fallback") else "No")

                items_written = summary.get("items")
                if items_written and isinstance(items_written, list):
                    _render_items_table(items_written, "Preview of items (from pipeline output)")
                else:
                    st.info("Items preview not returned by pipeline.")
                # Recent activity
                st.markdown("---")
                st.info(f"Last action: **Wrote AFSC {afsc_code}**. Open the *Explore KSAs* tab to view.")
                clear_all_caches()

# =========================
# Bulk JSONL ingest (Claude output)
# =========================
st.markdown("---")
st.subheader("Bulk JSONL ingest")
st.caption("Upload a JSONL with one AFSC per line (fields like: afsc, md, sections, source). Each line is processed via the pipeline.")

jsonl_file = st.file_uploader("Upload JSONL (one AFSC per line)", type=["jsonl"])
if jsonl_file is not None:
    if st.button("🚀 Ingest JSONL", use_container_width=True):
        try:
            _ = get_driver()
        except Exception as e:
            st.error(f"Neo4j connection error: {e}")
        else:
            lines = jsonl_file.getvalue().decode("utf-8").splitlines()
            total = len(lines)
            ok = fail = 0
            pb = st.progress(0)
            log = st.empty()
            with get_driver().session(database=NEO4J_DATABASE) as session:
                for i, line in enumerate(lines, start=1):
                    try:
                        obj = json.loads(line)
                        code = (obj.get("afsc") or "").strip()
                        text = obj.get("md") or json.dumps(obj.get("sections", {}), ensure_ascii=False)
                        if not code or not text:
                            fail += 1
                        else:
                            run_pipeline(
                                afsc_code=code,
                                afsc_raw_text=text,
                                neo4j_session=session,
                            )
                            ok += 1
                    except Exception:
                        fail += 1
                    pb.progress(min(i / total, 1.0))
                    log.text(f"Ingested {i}/{total} … success={ok}, fail={fail}")
                    time.sleep(0.01)
            clear_all_caches()
            st.success(f"Bulk ingest complete — success: {ok}, failed: {fail}. Open the Explore tab to verify.")

# =========================
# Danger zone
# =========================
with st.expander("Danger zone: delete AFSCs + their items", expanded=False):
    st.warning("This permanently deletes selected AFSC nodes and any now-orphaned Item nodes.")
    codes_text = st.text_area("AFSC codes (comma/space/newline separated)", placeholder="e.g. 1N1X1, 17S3X, 1D7")
    confirm_text = st.text_input("Type DELETE to enable the bulk delete")
    disabled = confirm_text.strip().upper() != "DELETE"
    if st.button("🧨 Delete selected AFSCs", disabled=disabled, use_container_width=True):
        codes = [c.strip() for c in re.split(r"[,\s]+", codes_text or "") if c.strip()]
        if not codes:
            st.error("Enter at least one AFSC code.")
        else:
            try:
                n = delete_afscs(codes)
                clear_all_caches()
                st.success(f"Deleted AFSCs: {', '.join(codes)} (count={n})")
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

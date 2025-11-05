#!/usr/bin/env python3
from __future__ import annotations
import re, json, os, argparse, pathlib
from typing import Dict, Any, List
from pypdf import PdfReader

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_DIR = REPO / "docs_text"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def clean_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"(?m)^(DAF?E?CD.*|Page\s+\d+)\s*$", "", s)
    s = s.replace("", "* ").replace("•", "* ").replace("", "* ").replace("", "* ")
    s = re.sub(r"(\w)\s*-\s*(\w)", r"\1-\2", s)
    s = re.sub(r"(\w)\s{2,}(\w)", r"\1 \2", s)
    s = re.sub(r"(\w)\s+([.,;:])", r"\1\2", s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()

def extract_pdf_text(path: pathlib.Path) -> str:
    reader = PdfReader(str(path))
    chunks: List[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            chunks.append("")
    return "\n\n".join(chunks)

AFECD_HEADER = re.compile(r"(?m)^\s*AFSC\s+([0-9A-Z]{2,5}[A-Z0-9X]{1,2})\s*,\s*(.+?)\s*$")
AFOCD_HEADER = AFECD_HEADER

def split_by_afsc(full_text: str, is_enlisted: bool) -> List[Dict[str, Any]]:
    header_re = AFECD_HEADER if is_enlisted else AFOCD_HEADER
    matches = list(header_re.finditer(full_text))
    if not matches:
        parts = []
        for block in re.split(r"(?m)^\s*AFSC\s+", full_text)[1:]:
            m = re.match(r"([0-9A-Z]{2,5}[A-Z0-9X]{1,2})\s*[, ]\s*(.*)", block, flags=re.S)
            if not m: 
                continue
            afsc = m.group(1).strip()
            rest = m.group(2).strip()
            parts.append({"afsc": afsc, "title": "", "text": "AFSC " + afsc + "\n" + rest})
        return parts

    out: List[Dict[str, Any]] = []
    for i, m in enumerate(matches):
        afsc = m.group(1).strip()
        title = m.group(2).strip()
        start = m.end()
        end = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
        section = full_text[start:end].strip()
        out.append({
            "afsc": afsc,
            "title": title,
            "text": f"AFSC {afsc}, {title}\n\n{section}".strip()
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to AFECD/AFOCD PDF")
    ap.add_argument("--type", choices=["AFECD","AFOCD"], required=True)
    ap.add_argument("--outbase", required=True, help="Base name for outputs (no extension)")
    args = ap.parse_args()

    pdf = pathlib.Path(args.pdf)
    raw = extract_pdf_text(pdf)
    cleaned = clean_text(raw)
    parts = split_by_afsc(cleaned, is_enlisted=(args.type=="AFECD"))

    out_jsonl = OUT_DIR / f"{args.outbase}.jsonl"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for p in parts:
            rec = {
                "afsc": p["afsc"],
                "title": p.get("title",""),
                "text": p["text"],
                "source_pdf": pdf.name,
                "doc_type": args.type,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    subdir = OUT_DIR / args.type
    subdir.mkdir(parents=True, exist_ok=True)
    for p in parts:
        afsc = p["afsc"]
        md = f"# AFSC {afsc} — {p.get('title','')}\n\n{p['text']}\n"
        (subdir / f"{afsc}.md").write_text(md, encoding="utf-8")

    print(f"Wrote {len(parts)} AFSC sections")
    print(f"- {out_jsonl}")
    print(f"- {subdir}/<AFSC>.md")

if __name__ == "__main__":
    main()

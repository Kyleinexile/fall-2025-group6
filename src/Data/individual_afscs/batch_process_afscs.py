"""
Batch process all 12 AFSC text files through the LAiSER + LLM pipeline.
Writes results to Neo4j and exports summary.
"""

import os
import sys
import time
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(REPO_ROOT / "src"))

from neo4j import GraphDatabase
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.extract_laiser import extract_ksa_items
from afsc_pipeline.enhance_llm import enhance_items_with_llm
from afsc_pipeline.graph_writer_v2 import upsert_afsc_and_items

# AFSC files mapping
AFSCS = {
    "1A3X1": "Mobility Force Aviator",
    "1C3": "All-Domain Command and Control Operations", 
    "1N0": "All Source Intelligence Analyst",
    "1N4": "Cyber Intelligence",
    "2A3": "Tactical Aircraft Maintenance",
    "2A5": "Airlift/Special Mission Aircraft Maintenance",
    "11F3": "Fighter Pilot",
    "12B": "Bomber Combat Systems Officer",
    "14F": "Information Operations",
    "14N": "Intelligence",
    "21A": "Aircraft Maintenance",
    "21M": "Munitions and Missile Maintenance",
}

# File paths - looks for .txt files in same directory as this script
AFSC_TEXT_DIR = Path(__file__).parent

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

def process_afsc(driver, afsc_code: str, afsc_title: str, text: str) -> dict:
    """Process a single AFSC through the pipeline."""
    print(f"\n{'='*60}")
    print(f"Processing: {afsc_code} - {afsc_title}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Step 1: Clean
    print("  [1/4] Cleaning text...")
    cleaned = clean_afsc_text(text)
    
    # Step 2: LAiSER extraction
    print("  [2/4] LAiSER extracting skills...")
    laiser_items = extract_ksa_items(cleaned)
    print(f"       → Found {len(laiser_items)} items")
    
    # Step 3: LLM enhancement
    print("  [3/4] LLM generating Knowledge/Abilities...")
    enhanced_items = enhance_items_with_llm(
        afsc_code=afsc_code,
        afsc_text=cleaned,
        items=laiser_items,
        max_new=6
    )
    print(f"       → Generated {len(enhanced_items)} K/A items")
    
    # Combine
    all_items = laiser_items + enhanced_items
    
    # Step 4: Write to Neo4j
    print("  [4/4] Writing to Neo4j...")
    with driver.session(database=NEO4J_DATABASE) as session:
        stats = upsert_afsc_and_items(
            session=session,
            afsc_code=afsc_code,
            items=all_items
        )
    
    elapsed = time.time() - start_time
    
    # Count by type
    k_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'knowledge')
    s_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'skill')
    a_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'ability')
    esco_count = sum(1 for i in all_items if getattr(i, 'esco_id', None))
    
    result = {
        "code": afsc_code,
        "title": afsc_title,
        "total": len(all_items),
        "knowledge": k_count,
        "skills": s_count,
        "abilities": a_count,
        "esco": esco_count,
        "laiser": len(laiser_items),
        "llm": len(enhanced_items),
        "time": elapsed
    }
    
    print(f"  ✓ Complete! {len(all_items)} KSAs in {elapsed:.1f}s")
    print(f"    K:{k_count} S:{s_count} A:{a_count} ESCO:{esco_count}")
    
    return result

def main():
    """Main batch processing function."""
    print("="*60)
    print("AFSC BATCH PROCESSOR")
    print("="*60)
    print(f"Processing {len(AFSCS)} AFSCs...")
    print(f"Neo4j: {NEO4J_URI}")
    print(f"Database: {NEO4J_DATABASE}")
    
    # Check text directory
    if not AFSC_TEXT_DIR.exists():
        print(f"\n❌ ERROR: Text directory not found: {AFSC_TEXT_DIR}")
        print("   Please create 'afsc_texts' folder with AFSC .txt files")
        return 1
    
    # Connect to Neo4j
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1").single()
        print("✓ Neo4j connected")
    except Exception as e:
        print(f"\n❌ ERROR: Neo4j connection failed: {e}")
        return 1
    
    # Process each AFSC
    results = []
    success = 0
    failed = 0
    
    for afsc_code, afsc_title in AFSCS.items():
        text_file = AFSC_TEXT_DIR / f"{afsc_code}.txt"
        
        if not text_file.exists():
            print(f"\n⚠️  WARNING: File not found: {text_file}")
            failed += 1
            continue
        
        try:
            text = text_file.read_text(encoding="utf-8")
            result = process_afsc(driver, afsc_code, afsc_title, text)
            results.append(result)
            success += 1
        except Exception as e:
            print(f"\n❌ ERROR processing {afsc_code}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            continue
    
    driver.close()
    
    # Summary
    print("\n" + "="*60)
    print("BATCH PROCESSING COMPLETE")
    print("="*60)
    print(f"Success: {success}/{len(AFSCS)}")
    print(f"Failed: {failed}/{len(AFSCS)}")
    
    if results:
        total_ksas = sum(r["total"] for r in results)
        total_time = sum(r["time"] for r in results)
        avg_per_afsc = total_ksas / len(results)
        
        print(f"\nTotal KSAs extracted: {total_ksas}")
        print(f"Average per AFSC: {avg_per_afsc:.1f}")
        print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
        
        print("\n" + "="*60)
        print("RESULTS BY AFSC:")
        print("="*60)
        for r in results:
            print(f"{r['code']:8} | {r['total']:3} KSAs | K:{r['knowledge']:2} S:{r['skills']:2} A:{r['abilities']:2} | ESCO:{r['esco']:2} | {r['time']:.1f}s")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

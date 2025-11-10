"""
Add titles to existing AFSC nodes in Neo4j
"""
import os
from neo4j import GraphDatabase

# AFSC titles from the text files
AFSC_TITLES = {
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
    "21M": "Munitions and Missile Maintenance"
}

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

def add_titles():
    """Add title property to all AFSC nodes"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session(database=NEO4J_DATABASE) as session:
        for code, title in AFSC_TITLES.items():
            result = session.run("""
                MATCH (a:AFSC {code: $code})
                SET a.title = $title
                RETURN a.code as code, a.title as title
            """, {"code": code, "title": title})
            
            record = result.single()
            if record:
                print(f"✓ Updated: {record['code']:8} → {record['title']}")
            else:
                print(f"✗ Not found: {code}")
    
    driver.close()
    print(f"\n✅ Updated {len(AFSC_TITLES)} AFSC titles")

if __name__ == "__main__":
    print("Adding titles to AFSC nodes...")
    print("=" * 60)
    add_titles()

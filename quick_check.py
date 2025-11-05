from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    # Check node types
    result = session.run("MATCH (n) RETURN DISTINCT labels(n)[0] as label, count(*) as count")
    print("\n=== Current Node Types ===")
    for record in result:
        print(f"  {record['label']}: {record['count']}")
    
    # Check relationships
    result = session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) as type, count(*) as count")
    print("\n=== Current Relationships ===")
    for record in result:
        print(f"  {record['type']}: {record['count']}")
    
    # Check if we have ESCO nodes
    result = session.run("MATCH (e:ESCOSkill) RETURN count(e) as count")
    esco_count = result.single()['count']
    print(f"\n=== ESCO Nodes: {esco_count} ===")

driver.close()
print("\n✅ Environment check complete!")
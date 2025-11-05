from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(os.getenv('NEO4J_URI'), auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))
session = driver.session()

# Check ALL relationships (incoming and outgoing)
result = session.run('MATCH (a:AFSC {code: "14N"})-[r]-() RETURN type(r) as rel_type, startNode(r) = a as is_outgoing, count(*) as count')
print('All relationships on 14N:')
for record in result:
    direction = "OUTGOING" if record['is_outgoing'] else "INCOMING"
    print(f"  {direction} {record['rel_type']}: {record['count']}")

driver.close()
from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'), 
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

session = driver.session()

print("Skills with OSN codes:")
print("=" * 80)

result = session.run('''
    MATCH (k:KSA)-[:ALIGNS_TO]->(e:ESCOSkill) 
    WHERE e.esco_id CONTAINS "OSN" 
    RETURN k.text as skill, e.esco_id as code 
    LIMIT 15
''')

for r in result:
    skill = r['skill'][:50]
    code = r['code']
    print(f"{skill:50} -> {code}")

driver.close()

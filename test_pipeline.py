import os
from dotenv import load_dotenv
load_dotenv()

print('=== Environment Check ===')
print(f'USE_LAISER: {os.getenv("USE_LAISER")}')
print(f'GEMINI_API_KEY set: {bool(os.getenv("GEMINI_API_KEY"))}')
print()

# Test just the extraction parts
from afsc_pipeline.extract_laiser import extract_ksa_items
from afsc_pipeline.enhance_llm import enhance_items_with_llm

test_text = '''
14N Intelligence Officer
Performs intelligence activities across the full range of military operations. 
Conducts collection management and target development.
Evaluates threat assessments and produces intelligence reports.
'''

print('=== Testing LAiSER Extraction ===')
laiser_items = extract_ksa_items(test_text)
print(f'Got {len(laiser_items)} items from LAiSER:\n')
for i in laiser_items:
    print(f'  {i.item_type:10} | {i.source:20} | ESCO: {i.esco_id or "None":10} | conf: {i.confidence:.3f}')
    print(f'    Text: {i.text[:60]}')

print('\n=== Testing LLM Enhancement ===')
llm_items = enhance_items_with_llm('14N', test_text, laiser_items)
print(f'Got {len(llm_items)} items from LLM:\n')
for i in llm_items:
    print(f'  {i.item_type:10} | {i.source:20} | conf: {i.confidence:.3f}')
    print(f'    Text: {i.text[:60]}')
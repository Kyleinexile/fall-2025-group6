import os
from dotenv import load_dotenv

load_dotenv()

print("=== Testing LAiSER ===")

try:
    from laiser.skill_extractor_refactored import SkillExtractorRefactored
    
    # Try with Gemini (you have the key!)
    print("\nInitializing LAiSER with Gemini...")
    se = SkillExtractorRefactored(
        model_id="gemini",
        api_key=os.getenv("GEMINI_API_KEY"),
        use_gpu=False
    )
    print("✅ LAiSER initialized!")
    
    # Check what methods exist
    print("\nAvailable methods:")
    methods = [m for m in dir(se) if not m.startswith('_')]
    for method in methods:
        print(f"  - {method}")
    
    # Test extraction with correct method
    test_text = "Performs intelligence data analysis and targeting operations."
    print(f"\nTest text: {test_text}")
    
    # Try the align_skills method (from the README we saw earlier)
    if hasattr(se, 'align_skills'):
        print("\nTrying align_skills method...")
        result = se.align_skills(raw_skills=[test_text], document_id="test")
        print(f"✅ Result:\n{result}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
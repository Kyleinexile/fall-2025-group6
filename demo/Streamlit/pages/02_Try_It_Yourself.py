import sys, pathlib, os, time
from typing import Optional

# Path setup
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Pipeline imports
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.extract_laiser import extract_ksa_items

st.set_page_config(page_title="Try It Yourself", page_icon="🔑", layout="wide")

# Initialize session state
if "user_api_key" not in st.session_state:
    st.session_state.user_api_key = None
if "user_provider" not in st.session_state:
    st.session_state.user_provider = None

# Main UI
st.title("🔑 Try It Yourself - BYO API Key")
st.markdown("**Run KSA extraction on your own AFSC text using your API key**")
st.caption("Your API key is stored in this session only and never saved to our database")

st.divider()

# API Key Configuration
st.markdown("### 1️⃣ Configure Your API Key")

col_provider, col_key = st.columns([1, 3])

with col_provider:
    provider = st.selectbox(
        "Provider",
        ["openai", "anthropic", "gemini"],
        help="Choose which LLM provider to use"
    )

with col_key:
    placeholder = {
        "openai": "sk-proj-...",
        "anthropic": "sk-ant-...",
        "gemini": "AIza..."
    }[provider]
    
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder=placeholder,
        help="Your API key is only stored in this browser session"
    )
    
    if api_key:
        st.session_state.user_api_key = api_key
        st.session_state.user_provider = provider

# Status indicator
has_key = st.session_state.user_api_key is not None

col_status, col_clear = st.columns([3, 1])
with col_status:
    if has_key:
        st.success(f"✅ API key loaded for {st.session_state.user_provider}")
    else:
        st.warning("⚠️ No API key provided")

with col_clear:
    if st.button("🗑️ Clear Key", use_container_width=True):
        st.session_state.user_api_key = None
        st.session_state.user_provider = None
        st.rerun()

st.divider()

# Text Input
st.markdown("### 2️⃣ Paste AFSC Text")

afsc_code = st.text_input(
    "AFSC Code (optional)",
    placeholder="e.g., 14N",
    help="Used for context in LLM prompts"
)

afsc_text = st.text_area(
    "AFSC Documentation",
    height=300,
    placeholder="Paste AFSC section text here (duties, responsibilities, specialty qualifications, etc.)...",
    help="Paste the text from an AFECD or AFOCD document"
)

# Settings Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")
    
    st.markdown("**LAiSER Settings**")
    use_laiser = st.checkbox("Enable LAiSER", value=True, help="Use LAiSER for skill extraction")
    laiser_topk = st.slider("LAiSER max items", 10, 30, 25)
    
    st.markdown("**LLM Settings**")
    max_llm_items = st.slider("Max K/A to generate", 3, 10, 6)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
    
    st.markdown("---")
    
    st.markdown("### 💡 Tips")
    st.caption("""
    **Best practices:**
    - Paste complete AFSC sections
    - Include duties AND qualifications
    - Longer text = better results
    - LAiSER finds skills with taxonomy codes
    - LLM generates knowledge & abilities
    """)

st.divider()

# Process Button
st.markdown("### 3️⃣ Run Extraction")

can_run = has_key and afsc_text.strip()

if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run, use_container_width=True):
    try:
        with st.status("Processing...", expanded=True) as status:
            # Step 1: Clean
            st.write("🧹 Cleaning text...")
            cleaned_text = clean_afsc_text(afsc_text)
            st.write(f"   ✓ Cleaned to {len(cleaned_text)} chars")
            time.sleep(0.2)
            
            # Step 2: LAiSER (if enabled)
            laiser_items = []
            if use_laiser:
                st.write("🔍 LAiSER extracting skills...")
                
                # Temporarily set environment for this extraction
                old_use_laiser = os.getenv("USE_LAISER")
                old_topk = os.getenv("LAISER_ALIGN_TOPK")
                
                os.environ["USE_LAISER"] = "true"
                os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)
                
                try:
                    laiser_items = extract_ksa_items(cleaned_text)
                    st.write(f"   ✓ Extracted {len(laiser_items)} skills")
                finally:
                    # Restore original env
                    if old_use_laiser:
                        os.environ["USE_LAISER"] = old_use_laiser
                    if old_topk:
                        os.environ["LAISER_ALIGN_TOPK"] = old_topk
                
                time.sleep(0.2)
            else:
                st.write("⏭️ LAiSER disabled, skipping skill extraction")
            
            # Step 3: LLM Enhancement
            st.write("🤖 LLM generating Knowledge/Abilities...")
            
            # Import and configure LLM
            from afsc_pipeline.enhance_llm import run_llm
            
            # Build hints from LAiSER items
            hints = []
            if laiser_items:
                skills = [item.text for item in laiser_items[:10]]  # Top 10 as hints
                hints = skills
            
            # Build prompt
            context = f"AFSC: {afsc_code or 'Unknown'}\n\n{cleaned_text[:2000]}"
            
            prompt = f"""Extract {max_llm_items} items from this Air Force job description.

Context:
{context}

Extracted Skills (use as hints):
{chr(10).join(f'- {h}' for h in hints[:5]) if hints else '(none)'}

Generate exactly {max_llm_items} items total:
- {max_llm_items // 2} Knowledge items (theoretical understanding needed)
- {max_llm_items // 2} Ability items (cognitive/physical capacities)

Format EACH as JSON on separate lines:
{{"type": "knowledge", "text": "..."}}
{{"type": "ability", "text": "..."}}

Requirements:
- Must be SPECIFIC to this role
- NO generic statements
- NO duplicates
- CONCISE (under 100 chars each)"""

            # Call LLM with user's key
            try:
                import json
                
                response_text = run_llm(
                    prompt=prompt,
                    provider=st.session_state.user_provider,
                    api_key=st.session_state.user_api_key,
                    temperature=temperature
                )
                
                # Parse response
                enhanced_items = []
                for line in response_text.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            obj = json.loads(line)
                            enhanced_items.append({
                                'type': obj.get('type', 'knowledge'),
                                'text': obj.get('text', ''),
                                'confidence': 0.7,
                                'source': f'llm-{st.session_state.user_provider}'
                            })
                        except:
                            pass
                
                st.write(f"   ✓ Generated {len(enhanced_items)} K/A items")
                time.sleep(0.2)
                
            except Exception as e:
                st.error(f"LLM call failed: {e}")
                enhanced_items = []
            
            status.update(label="✅ Complete!", state="complete")
        
        # Combine results
        all_items = []
        
        # Add LAiSER items
        for item in laiser_items:
            all_items.append({
                'Type': 'skill',
                'Text': item.text,
                'Confidence': float(getattr(item, 'confidence', 0.0)),
                'Source': getattr(item, 'source', 'laiser'),
                'Taxonomy': getattr(item, 'esco_id', '') or ''
            })
        
        # Add LLM items
        for item in enhanced_items:
            all_items.append({
                'Type': item['type'],
                'Text': item['text'],
                'Confidence': item['confidence'],
                'Source': item['source'],
                'Taxonomy': ''
            })
        
        if not all_items:
            st.warning("No items extracted. Try enabling LAiSER or adjusting settings.")
            st.stop()
        
        # Display Results
        st.success(f"✅ Extracted {len(all_items)} KSAs")
        st.balloons()
        
        # Metrics
        k_count = sum(1 for i in all_items if i['Type'] == 'knowledge')
        s_count = sum(1 for i in all_items if i['Type'] == 'skill')
        a_count = sum(1 for i in all_items if i['Type'] == 'ability')
        tax_count = sum(1 for i in all_items if i['Taxonomy'])
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total KSAs", len(all_items))
        col2.metric("Knowledge", k_count)
        col3.metric("Skills", s_count)
        col4.metric("Abilities", a_count)
        col5.metric("Taxonomy Aligned", tax_count)
        
        # Results Table
        st.markdown("### 📊 Extracted KSAs")
        
        df = pd.DataFrame(all_items)
        
        # Add filters
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            type_filter = st.multiselect(
                "Filter by type",
                ['knowledge', 'skill', 'ability'],
                default=['knowledge', 'skill', 'ability']
            )
        with col_filter2:
            min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)
        
        # Apply filters
        filtered_df = df[df['Type'].isin(type_filter)]
        filtered_df = filtered_df[filtered_df['Confidence'] >= min_conf]
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
        
        # Display
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confidence": st.column_config.NumberColumn(format="%.2f"),
                "Taxonomy": st.column_config.TextColumn("Taxonomy Code")
            }
        )
        
        # Export
        st.markdown("### 💾 Export Results")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                "⬇️ Download Filtered CSV",
                csv,
                f"{afsc_code or 'extracted'}_ksas.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            full_csv = df.to_csv(index=False)
            st.download_button(
                "⬇️ Download All CSV",
                full_csv,
                f"{afsc_code or 'extracted'}_ksas_full.csv",
                "text/csv",
                use_container_width=True
            )
        
        st.info("💡 **Note:** These results are NOT saved to the database. This is a demo/testing tool only.")
        
    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc())

# Help Section
with st.expander("❓ How to Use This Tool"):
    st.markdown("""
    ### Step-by-Step Guide
    
    1. **Get an API Key**
       - OpenAI: https://platform.openai.com/api-keys
       - Anthropic: https://console.anthropic.com/settings/keys
       - Google Gemini: https://aistudio.google.com/app/apikey
    
    2. **Choose Your Provider**
       - Select from OpenAI, Anthropic, or Gemini
       - Paste your API key (stored in session only)
    
    3. **Paste AFSC Text**
       - Copy text from AFECD/AFOCD documents
       - Include duties, responsibilities, qualifications
       - More text = better results
    
    4. **Run Extraction**
       - LAiSER extracts skills with taxonomy codes
       - LLM generates knowledge and abilities
       - Results display immediately
    
    5. **Download Results**
       - Export as CSV for analysis
       - Filter by type or confidence
       - Results are NOT saved to database
    
    ### Privacy & Security
    
    - ✅ Your API key is stored in browser session only
    - ✅ Never saved to our servers or database
    - ✅ Cleared when you close the browser
    - ✅ You control API costs directly
    
    ### Comparison with Admin Tools
    
    **This Tool (BYO-API):**
    - No database writes
    - Use your own API key
    - Immediate results
    - Download only
    
    **Admin Tools:**
    - Writes to database
    - Uses system credentials
    - Permanent storage
    - Full pipeline integration
    """)

st.divider()
st.caption("🔑 Try It Yourself | No database writes | Session-only API keys")

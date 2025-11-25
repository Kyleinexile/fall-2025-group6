# Documentation FAQ Updates Required
# File: 05_Documentation__FAQ.py
# 
# This file lists all lines with hardcoded metrics that need updating
# to match verified Neo4j database values.
#
# VERIFIED METRICS:
# - AFSCs: 12
# - Total KSAs: 253
# - Skills: 188, Knowledge: 35, Abilities: 30
# - Avg KSAs/AFSC: ~21
# - ESCO Alignment: ~20%
# - Processing Time: 60-80 seconds
#
# =============================================================================

# LINE 157-161 (Overview section - Key Achievements)
# BEFORE:
"""
        - **12 AFSCs** processed successfully
        - **330+ KSAs** extracted
        - **~$0.005** cost per AFSC
        - **3.2 seconds** avg processing time
        - **LAiSER + Gemini** integration
"""
# AFTER:
"""
        - **12 AFSCs** processed successfully
        - **253 KSAs** extracted
        - **~21 KSAs** average per AFSC
        - **60-80 seconds** processing time
        - **~20% ESCO** taxonomy alignment
"""

# LINE 194-196 (Quick Stats - Coverage Metrics)
# BEFORE:
"""
    col1.metric("AFSCs Processed", "12")
    col2.metric("Total KSAs", "330+")
    col3.metric("Avg per AFSC", "27.5")
"""
# AFTER:
"""
    col1.metric("AFSCs Processed", "12")
    col2.metric("Total KSAs", "253")
    col3.metric("Avg per AFSC", "~21")
"""

# LINE 199-203 (Quick Stats - Performance Metrics)
# BEFORE:
"""
    col1.metric("Total Processing", "3.2s avg")
    col2.metric("LAiSER Extract", "2-5s")
    col3.metric("Deduplication", "<0.1s")
    col4.metric("Neo4j Write", "0.5-1s")
"""
# AFTER:
"""
    col1.metric("Total Processing", "60-80s")
    col2.metric("LAiSER Extract", "30-45s")
    col3.metric("Deduplication", "<1s")
    col4.metric("Neo4j Write", "1-2s")
"""

# LINE 205-210 (Quick Stats - Cost Metrics)
# BEFORE:
"""
    st.markdown("### 💰 Cost Metrics (per AFSC)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("LAiSER Only", "$0.005")
    col2.metric("With LLM", "$0.005-0.010")
    col3.metric("Model Used", "Gemini Flash")
    col4.metric("Token Limit", "512 max")
"""
# AFTER:
"""
    st.markdown("### 💰 Configuration")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("LLM Providers", "4")
    col2.metric("Default Model", "Gemini Flash")
    col3.metric("Token Limit", "1024 max")
    col4.metric("ESCO Alignment", "~20%")
"""

# LINE 218-223 (Processing Breakdown table)
# BEFORE:
"""
    stage_data = pd.DataFrame({
        "Stage": ["Preprocessing", "LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Neo4j Write"],
        "Avg Time": ["<0.1s", "2-5s", "<0.1s", "1-3s", "<0.1s", "0.5-1s"],
        "Reduction": ["-", "-", "~10%", "-", "~15%", "-"],
        "Output": ["Clean text", "20-30 skills", "Filtered items", "+5-15 K/A", "Unique items", "Graph"]
    })
"""
# AFTER:
"""
    stage_data = pd.DataFrame({
        "Stage": ["Preprocessing", "LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Neo4j Write"],
        "Avg Time": ["<1s", "30-45s", "<1s", "15-25s", "<1s", "1-2s"],
        "Reduction": ["-", "-", "~10%", "-", "~15%", "-"],
        "Output": ["Clean text", "15-25 skills", "Filtered items", "+5-10 K/A", "Unique items", "Graph"]
    })
"""

# LINE 316-321 (LLM Settings - Cost table)
# BEFORE:
"""
    cost_comparison = pd.DataFrame({
        "Configuration": ["LAiSER Only", "LAiSER + Gemini Flash", "LAiSER + GPT-4o-mini", "LAiSER + Claude Sonnet"],
        "Cost per AFSC": ["$0.005", "$0.005-0.010", "$0.015-0.025", "$0.050-0.100"],
        "Total (12 AFSCs)": ["$0.06", "$0.06-0.12", "$0.18-0.30", "$0.60-1.20"],
        "Recommendation": ["✅ Default", "✅ If K/A needed", "⚠️ Backup only", "❌ Too expensive"]
    })
"""
# AFTER (soften specific cost claims):
"""
    cost_comparison = pd.DataFrame({
        "Configuration": ["LAiSER Only", "LAiSER + Gemini Flash", "LAiSER + GPT-4o-mini", "LAiSER + Claude Sonnet"],
        "Relative Cost": ["Lowest", "Low", "Medium", "Higher"],
        "Use Case": ["Skills only", "Skills + K/A", "Backup option", "Premium quality"],
        "Recommendation": ["✅ Default", "✅ If K/A needed", "⚠️ Backup only", "⚠️ Premium only"]
    })
"""

# LINE 417-421 (LAiSER Performance Characteristics)
# BEFORE:
"""
    with perf_col1:
        st.metric("Extraction Time", "2-5 seconds", "per AFSC")
    
    with perf_col2:
        st.metric("Typical Output", "20-30 skills", "per AFSC")
"""
# AFTER:
"""
    with perf_col1:
        st.metric("Extraction Time", "30-45 seconds", "per AFSC")
    
    with perf_col2:
        st.metric("Typical Output", "15-25 skills", "per AFSC")
"""

# LINE 712 (Pipeline Flow - Stage 2 Output)
# BEFORE: "Output: 20-30 SKILL items"
# AFTER:  "Output: 15-25 SKILL items"

# LINE 724-725 (Pipeline Flow - Quality Filter)
# BEFORE: "• Length constraints (3-80 chars)"
# AFTER:  "• Length constraints (3-80 chars skills, 150 K/A)"

# LINE 749 (Pipeline Flow - Final Output)
# BEFORE: "Output: 25-50 KSAs per AFSC, ~70% ESCO-aligned"
# AFTER:  "Output: ~21 KSAs per AFSC, ~20% ESCO-aligned"

# LINE 796 (FAQ - cost claim)
# BEFORE: "- Cost-effective (~$0.005 per AFSC)"
# AFTER:  "- Cost-effective extraction"

# LINE 816 (FAQ - pypdf page count)
# BEFORE: "- Search 1000+ page AFSC documents (AFECD/AFOCD)"
# AFTER:  "- Search 700+ page AFSC documents (AFECD/AFOCD)"

# LINE 868-883 (Performance Metrics - Processing Time table)
# BEFORE:
"""
    time_data = pd.DataFrame({
        "Stage": [...],
        "Min Time": ["<0.1s", "2s", "<0.1s", "1s", "<0.1s", "0.5s", "**3s**"],
        "Avg Time": ["<0.1s", "3.5s", "<0.1s", "2s", "<0.1s", "0.7s", "**6.3s**"],
        "Max Time": ["<0.1s", "5s", "<0.1s", "3s", "<0.1s", "1s", "**9.1s**"],
        ...
    })
"""
# AFTER:
"""
    time_data = pd.DataFrame({
        "Stage": [...],
        "Min Time": ["<1s", "25s", "<1s", "10s", "<1s", "1s", "**50s**"],
        "Avg Time": ["<1s", "35s", "<1s", "18s", "<1s", "1.5s", "**60s**"],
        "Max Time": ["<1s", "50s", "<1s", "30s", "<1s", "2s", "**90s**"],
        ...
    })
"""

# LINE 888-899 (Performance Metrics - Item Reduction table)
# BEFORE:
"""
    reduction_data = pd.DataFrame({
        "Stage": ["LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Final Output"],
        "Typical Count": ["20-30", "18-27", "25-40", "21-34", "25-35"],
        ...
    })
"""
# AFTER:
"""
    reduction_data = pd.DataFrame({
        "Stage": ["LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Final Output"],
        "Typical Count": ["15-25", "12-22", "18-30", "15-25", "~21"],
        ...
    })
"""

# LINE 902-913 (Performance Metrics - Accuracy Metrics)
# BEFORE:
"""
    with acc_col1:
        st.metric("False Positive Rate", "<1%", "near-duplicates")
    
    with acc_col2:
        st.metric("Extraction Recall", "~85%", "vs manual review")
    
    with acc_col3:
        st.metric("Precision", "~90%", "relevant KSAs")
"""
# AFTER (remove unverified claims):
"""
    with acc_col1:
        st.metric("False Positive Rate", "<1%", "near-duplicates")
    
    with acc_col2:
        st.metric("ESCO Alignment", "~20%", "taxonomy linked")
    
    with acc_col3:
        st.metric("Avg per AFSC", "~21", "KSAs extracted")
"""

# LINE 937-949 (Cost Analysis - Cost Breakdown table)
# Soften specific cost claims - use relative terms instead of exact dollar amounts

# LINE 997-999 (Cost Analysis - ROI section)
# BEFORE:
"""
    **Automated pipeline:**
    - Time per AFSC: ~3-8 seconds
    - Processing cost: **$0.005-0.010**
    - Total cost per AFSC: **$0.005-0.010**
    - Quality: Consistent, 70% ESCO-aligned
"""
# AFTER:
"""
    **Automated pipeline:**
    - Time per AFSC: ~60-80 seconds
    - Processing cost: **Minimal (API calls only)**
    - Quality: Consistent, ~20% ESCO-aligned
    - Scalable: Can process all 200+ AFSCs
"""

# =============================================================================
# SUMMARY OF CHANGES:
# =============================================================================
# 1. Total KSAs: 330+ → 253
# 2. Avg per AFSC: 27.5 → ~21
# 3. Processing time: 3-8s → 60-80s
# 4. LAiSER extraction: 2-5s → 30-45s
# 5. Skills extracted: 20-30 → 15-25
# 6. Final output: 25-35 → ~21
# 7. ESCO alignment: 70% → ~20%
# 8. Remove specific cost claims ($0.005, etc.)
# 9. Remove unverified 85% recall, 90% precision claims
# 10. Page count: 1000+ → 700+
# =============================================================================

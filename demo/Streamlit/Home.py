import streamlit as st
import os
import base64
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="USAF KSA Explorer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# HELPER FUNCTION - Convert image to base64
# ============================================================================
def get_base64_image(image_path):
    """Convert an image file to base64 string for embedding in CSS"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.warning(f"Could not load background image: {e}")
        return None

# ============================================================================
# LOAD BACKGROUND IMAGE
# ============================================================================
current_dir = Path(__file__).parent
bg_image_path = current_dir / "assets" / "AFDOGGO.jpg"
bg_image_base64 = get_base64_image(bg_image_path)

# ============================================================================
# CUSTOM CSS - Air Force Theme & Professional Styling
# ============================================================================
# Build CSS with background image if available
background_css = ""
if bg_image_base64:
    background_css = f"""
    /* Semi-transparent Background Image */
    .main {{
        background-image: url('data:image/jpeg;base64,{bg_image_base64}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
        position: relative;
    }}
    
    .main::before {{
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(255, 255, 255, 0.95);
        z-index: -1;
        pointer-events: none;
    }}
    """

st.markdown(f"""
<style>
    /* Import Professional Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    {background_css}
    
    /* Global Font & Typography */
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        font-size: 15px;
    }}
    
    /* Air Force Blue Theme - Aggressive Button Styling */
    .stButton>button[kind="primary"],
    button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {{
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }}
    .stButton>button[kind="primary"]:hover {{
        background-color: #003D7A !important;
        color: #FFFFFF !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.4) !important;
    }}
    .stButton>button[kind="primary"] p,
    .stButton>button[kind="primary"] span,
    .stButton>button[kind="primary"] div {{
        color: #FFFFFF !important;
    }}
    
    .stButton>button[kind="secondary"],
    button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {{
        background-color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        color: #00539B !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }}
    .stButton>button[kind="secondary"]:hover {{
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.3) !important;
    }}
    .stButton>button[kind="secondary"] p,
    .stButton>button[kind="secondary"] span,
    .stButton>button[kind="secondary"] div {{
        color: inherit !important;
    }}
    
    /* Metrics Styling - Bigger and Bolder */
    [data-testid="stMetricValue"] {{
        font-size: 42px;
        font-weight: 800;
        color: #00539B;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 14px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    
    /* Headers */
    h1 {{
        color: #1F2937;
        font-weight: 800;
        letter-spacing: -0.5px;
    }}
    h2 {{
        color: #374151;
        font-weight: 700;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }}
    h3 {{
        color: #1F2937;
        font-weight: 600;
    }}
    
    /* Thicker Dividers */
    hr {{
        border: none;
        border-top: 3px solid #E5E7EB;
        margin: 3rem 0;
    }}
    
    /* Better Typography */
    p {{
        line-height: 1.6;
        color: #4B5563;
    }}
    
    /* Status Badge */
    .status-badge {{
        display: inline-block;
        padding: 6px 16px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
        margin-right: 8px;
        margin-bottom: 8px;
    }}
    .status-success {{
        background-color: #D1FAE5;
        color: #065F46;
    }}
    .status-warning {{
        background-color: #FEF3C7;
        color: #92400E;
    }}
    .status-error {{
        background-color: #FEE2E2;
        color: #991B1B;
    }}
    
    /* Splash Screen Animation */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    .splash-container {{
        animation: fadeInUp 0.8s ease-out;
    }}
    .splash-image {{
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
        margin-bottom: 2rem;
    }}
    
    /* Pipeline Step Boxes */
    .pipeline-step {{
        background: white;
        border: 3px solid #00539B;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        transition: all 0.3s ease;
    }}
    .pipeline-step:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0, 83, 155, 0.2);
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SPLASH SCREEN
# ============================================================================
if 'entered' not in st.session_state:
    st.session_state.entered = False

if not st.session_state.entered:
    st.markdown("<div class='splash-container'>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Air Force Image
        current_dir = Path(__file__).parent
        image_path = current_dir / "assets" / "air force.jpg"
        
        if image_path.exists():
            st.markdown("<div class='splash-image'>", unsafe_allow_html=True)
            st.image(str(image_path), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Branding
        st.markdown("""
        <div style='text-align: center;'>
            <h1 style='
                font-size: 3.5rem; 
                font-weight: 800; 
                color: #00539B; 
                margin-bottom: 0.5rem;
                letter-spacing: -1px;
            '>
                USAF KSA Explorer
            </h1>
            <p style='
                font-size: 1.3rem; 
                color: #6B7280; 
                font-weight: 500;
                margin-bottom: 2.5rem;
            '>
                Air Force Specialty Code Intelligence & Career Mapping
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Enter Button
        if st.button("🚀 Enter Application", use_container_width=True, type="primary", key="enter_app"):
            st.session_state.entered = True
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ============================================================================
# NEO4J CONNECTION CHECK
# ============================================================================
@st.cache_resource
def get_neo4j_status():
    """Check Neo4j and API key availability"""
    status = {
        'neo4j': False,
        'gemini': bool(os.getenv('GEMINI_API_KEY')),
        'openai': bool(os.getenv('OPENAI_API_KEY')),
        'anthropic': bool(os.getenv('ANTHROPIC_API_KEY'))
    }
    
    try:
        uri = os.getenv('NEO4J_URI')
        user = os.getenv('NEO4J_USER')
        password = os.getenv('NEO4J_PASSWORD')
        
        if uri and user and password:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            driver.close()
            status['neo4j'] = True
    except Exception:
        pass
    
    return status

status = get_neo4j_status()

# ============================================================================
# HERO SECTION
# ============================================================================
st.markdown("""
<div style='text-align: center; padding: 1.5rem 0;'>
    <h1 style='font-size: 3rem; font-weight: 800; color: #00539B; margin-bottom: 0.5rem;'>
        🚀 USAF KSA Extraction Pipeline
    </h1>
    <p style='font-size: 1.2rem; color: #6B7280; font-weight: 500;'>
        From Air Force specialty documents to transferable career insights
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 2rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# KEY METRICS
# ============================================================================
st.markdown("## 📊 System Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="AFSCs Processed",
        value="30+",
        delta="Officer & Enlisted"
    )

with col2:
    st.metric(
        label="KSA Items Extracted",
        value="600+",
        delta="Per AFSC average: 25-30"
    )

with col3:
    st.metric(
        label="ESCO Taxonomy Mappings",
        value="1000+",
        delta="EU skills framework"
    )

with col4:
    db_status = "🟢 Connected" if status['neo4j'] else "🔴 Offline"
    st.metric(
        label="Database Status",
        value=db_status,
        delta="Neo4j Graph DB"
    )

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# GETTING STARTED
# ============================================================================
if 'hide_getting_started' not in st.session_state:
    st.session_state.hide_getting_started = False

if not st.session_state.hide_getting_started:
    st.markdown("## 🎯 Getting Started")
    st.markdown("""
    <div style='background-color: #EFF6FF; padding: 1.5rem; border-radius: 12px; border-left: 6px solid #00539B;'>
        <p style='font-size: 1rem; color: #1F2937; margin-bottom: 1rem; line-height: 1.6;'>
            <strong>Welcome to the USAF KSA Explorer!</strong> This tool maps Air Force specialty codes to 
            Knowledge, Skills, and Abilities (KSAs) for career planning and transition insights.
        </p>
        <p style='font-size: 0.95rem; color: #4B5563; margin-bottom: 1rem; line-height: 1.6;'>
            <strong>Quick Start:</strong>
        </p>
        <ul style='color: #4B5563; font-size: 0.95rem; line-height: 1.6; margin-left: 1.5rem;'>
            <li><strong>Explore KSAs</strong> → Browse AFSCs and view extracted skills</li>
            <li><strong>Try It Yourself</strong> → Test the extraction with your own API key</li>
            <li><strong>Admin Tools</strong> → Process documents and manage the database</li>
        </ul>
        <p style='font-size: 0.9rem; color: #6B7280; margin-top: 1rem; margin-bottom: 0;'>
            💡 <em>Tip: Check the "Learn More" section below for KSA definitions and tech stack details</em>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col_dismiss, col_spacer = st.columns([1, 5])
    with col_dismiss:
        if st.button("✕ Dismiss", key="dismiss_getting_started", type="secondary"):
            st.session_state.hide_getting_started = True
            st.rerun()

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# WHAT WOULD YOU LIKE TO DO?
# ============================================================================
st.markdown("## 🚀 What would you like to do?")
st.markdown("<p style='color: #6B7280; font-size: 1.05rem; margin-bottom: 2rem;'>Choose your workflow below</p>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    with st.container():
        st.markdown("### 🔍 Explore KSAs")
        st.markdown("Browse AFSCs, view extracted Knowledge, Skills, and Abilities, and find overlaps between specialties.")
        st.caption("→ Read-only insights & cross-AFSC analysis")
        if st.button("Open Explore KSAs →", use_container_width=True, type="primary", key="explore"):
            st.switch_page("pages/03_Explore_KSAs.py")

with col2:
    with st.container():
        st.markdown("### 🔑 Try It Yourself")
        st.markdown("Paste AFSC text and generate Knowledge/Ability items using your own API key for testing.")
        st.caption("→ Sandbox with your own API key")
        if st.button("Open Try It Yourself →", use_container_width=True, type="secondary", key="byo"):
            st.switch_page("pages/02_Try_It_Yourself.py")

with col3:
    with st.container():
        st.markdown("### ⚙️ Admin Tools")
        st.markdown("Process PDFs/Markdown, run extraction pipeline, and manage database content.")
        st.caption("→ Power tools for data management")
        if st.button("Open Admin Tools →", use_container_width=True, type="secondary", key="admin"):
            st.switch_page("pages/04_Admin_Tools.py")

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# HOW IT WORKS - 6 Steps with Boxes
# ============================================================================
st.markdown("## 🔄 How it works")

# 6-step pipeline with boxes
col1, arr1, col2, arr2, col3, arr3, col4, arr4, col5, arr5, col6 = st.columns([1, 0.15, 1, 0.15, 1, 0.15, 1, 0.15, 1, 0.15, 1])

with col1:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📄</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>1. Ingest</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Load AFOCD/AFECD documents</p>
    </div>
    """, unsafe_allow_html=True)

with arr1:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🧹</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>2. Preprocess</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Clean & normalize text</p>
    </div>
    """, unsafe_allow_html=True)

with arr2:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🤖</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>3. Extract</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>LAiSER skill extraction</p>
    </div>
    """, unsafe_allow_html=True)

with arr3:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>✨</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>4. Enhance</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>LLM K/A generation</p>
    </div>
    """, unsafe_allow_html=True)

with arr4:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>💾</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>5. Store</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Neo4j graph database</p>
    </div>
    """, unsafe_allow_html=True)

with arr5:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col6:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🌐</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>6. Explore</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Interactive web interface</p>
    </div>
    """, unsafe_allow_html=True)

with st.expander("See detailed pipeline steps"):
    st.markdown("""
    ### Detailed Process
    
    1. **Ingest** • Upload AFSC documents (AFOCD/AFECD) or use pre-split Markdown
    2. **Preprocess** • Clean text, remove formatting artifacts, normalize structure
    3. **Extract** • LAiSER generates baseline KSAs with confidence scores and ESCO taxonomy IDs
    4. **Enhance** • LLMs (Gemini/Claude/OpenAI) add complementary Knowledge/Ability items
    5. **Store** • Write AFSCs, KSAs, and relationships into Neo4j graph database
    6. **Explore** • Query, compare AFSCs, find skill overlaps, and export analysis tables
    
    **Performance:** ~5-10 seconds per AFSC | **Accuracy:** 85%+ precision on validated samples
    """)

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# LEARN MORE
# ============================================================================
with st.expander("📖 Learn More (About • KSA Definitions • Tech Stack • Configuration)"):
    st.markdown("### About This Project")
    st.write(
        "This is a GWU Data Science Capstone project that maps **Air Force Specialty Code (AFSC)** "
        "descriptions to transferable **Knowledge, Skills, and Abilities (KSAs)** for career analysis, "
        "planning, and transition insights."
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### KSA Definitions")
    col_k, col_s, col_a = st.columns(3)
    
    with col_k:
        st.markdown("**📖 Knowledge**")
        st.markdown("A body of facts, concepts, and procedures necessary to perform tasks effectively.")
        st.caption("Example: Intelligence cycle fundamentals")
    
    with col_s:
        st.markdown("**🛠️ Skills**")
        st.markdown("Learned capacities to perform specific tasks or activities.")
        st.caption("Example: Perform intelligence analysis")
    
    with col_a:
        st.markdown("**💪 Abilities**")
        st.markdown("Enduring capabilities that enable performance across contexts.")
        st.caption("Example: Synthesize multi-source data")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### Tech Stack (High Level)")
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        st.markdown("**🤖 AI/ML**")
        st.markdown("""
        - LAiSER (GWU) - Skill extraction
        - Gemini 1.5 Flash - Primary LLM
        - Claude Sonnet 4 - Fallback LLM
        - OpenAI GPT-4 - Optional
        """)
    
    with col_t2:
        st.markdown("**💾 Data**")
        st.markdown("""
        - Neo4j Aura - Graph database
        - ESCO Taxonomy - EU skills framework
        - LAiSER Taxonomy - Extended codes
        - Python 3.11 - Core language
        """)
    
    with col_t3:
        st.markdown("**🌐 Interface**")
        st.markdown("""
        - Streamlit - Multi-page web app
        - GitHub - Version control
        - Streamlit Cloud - Hosting
        - Custom CSS - Air Force theme
        """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### System Configuration (Quick Check)")
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        st.markdown("**Environment Status**")
        st.code(f"""
Neo4j: {'✅ Connected' if status['neo4j'] else '❌ Not configured'}
Gemini API: {'✅ Set' if status['gemini'] else '⚠️ Missing'}
OpenAI API: {'✅ Set' if status['openai'] else '⚠️ Missing'}
Anthropic API: {'✅ Set' if status['anthropic'] else '⚠️ Missing'}
        """)
    
    with col_cfg2:
        st.markdown("**Next Steps**")
        st.markdown("""
        - **Explore existing data** → Explore KSAs page
        - **Test extraction** → Try It Yourself page
        - **Process documents** → Admin Tools page
        - **View documentation** → System Configuration expander
        """)

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; padding: 2rem 0; color: #6B7280; font-size: 0.9rem;'>
    <p style='margin-bottom: 0.5rem;'>
        <strong style='color: #00539B;'>🚀 USAF KSA Extraction Pipeline</strong>
    </p>
    <p style='margin: 0;'>
        © 2025 George Washington University | MS Data Science Capstone
    </p>
</div>
""", unsafe_allow_html=True)

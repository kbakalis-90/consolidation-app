"""Streamlit entrypoint. Run with: streamlit run app.py"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Consolidation & Reporting", page_icon="📈", layout="wide")

pages = [
    st.Page("ui/pages/1_Setup.py", title="Setup", icon="⚙️"),
    st.Page("ui/pages/2_Upload.py", title="Upload", icon="📤"),
    st.Page("ui/pages/3_Entity_Statements.py", title="Entity Statements", icon="📊"),
    st.Page("ui/pages/4_Consolidation.py", title="Consolidation", icon="🌍"),
]

st.navigation(pages).run()

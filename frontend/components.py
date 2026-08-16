import streamlit as st
from config import APP_TITLE, APP_SUBTITLE

EXAMPLE_QUERIES = [
    "What is the revenue trend for the last 4 quarters?",
    "Compare gross margins across product categories",
    "Show me the top 10 stores by sales performance",
    "Analyze SKU-level profitability for the hair care segment",
]


def render_header():
    """Render the app header."""
    st.markdown(f"### {APP_TITLE}")
    st.caption(APP_SUBTITLE)


def render_empty_state():
    """Render a placeholder when no thread is selected."""
    st.markdown('<div class="empty-state">', unsafe_allow_html=True)
    st.markdown("## Start a Conversation")
    st.markdown("Select a thread from the sidebar or create a new one.")
    st.divider()
    st.markdown("**Try asking:**")

    cols = st.columns(2)
    for i, query in enumerate(EXAMPLE_QUERIES):
        with cols[i % 2]:
            if st.button(query, key=f"example_{i}", use_container_width=True):
                st.session_state._pending_example_query = query
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

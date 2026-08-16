import streamlit as st

st.set_page_config(
    page_title="GCPL Financial Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from state import init_session_state, is_authenticated
from styles import apply_styles
from auth import render_login
from sidebar import render_sidebar
from chat import render_chat
from components import render_header, render_empty_state

init_session_state()
apply_styles()

if not is_authenticated():
    render_login()
    st.stop()

render_sidebar()
render_header()

if st.session_state.current_thread_id:
    render_chat()
else:
    render_empty_state()

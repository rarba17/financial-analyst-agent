import streamlit as st


def init_session_state():
    """Initialize all session state keys with defaults."""
    defaults = {
        # Auth
        "token": None,
        "user_id": None,
        "email": None,
        "name": None,
        "is_admin": False,
        # Threads
        "current_thread_id": None,
        "threads": [],
        # Chat
        "messages": [],
        "waiting_for_response": False,
        "pending_ai_message_id": None,
        # UI
        "auth_step": "email",  # "email" or "otp"
        "auth_email": "",
        "error_message": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_auth_state():
    """Clear authentication state (on logout or 401)."""
    st.session_state.token = None
    st.session_state.user_id = None
    st.session_state.email = None
    st.session_state.name = None
    st.session_state.is_admin = False
    st.session_state.current_thread_id = None
    st.session_state.threads = []
    st.session_state.messages = []
    st.session_state.waiting_for_response = False
    st.session_state.pending_ai_message_id = None
    st.session_state.auth_step = "email"
    st.session_state.auth_email = ""
    st.session_state.error_message = None


def is_authenticated() -> bool:
    return st.session_state.get("token") is not None

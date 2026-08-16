import streamlit as st
from api_client import get_threads, create_thread, create_share, clear_messages, SessionExpiredError
from state import clear_auth_state


def render_sidebar():
    """Render the sidebar with thread management."""
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.name or st.session_state.email}")
        st.divider()

        # ── New Thread ───────────────────────────────────────────────────
        with st.expander("New Thread", expanded=False):
            title = st.text_input("Thread title", key="new_thread_title")
            if st.button("Create", use_container_width=True, key="create_thread_btn"):
                if title.strip():
                    try:
                        thread = create_thread(title.strip())
                        st.session_state.current_thread_id = thread["id"]
                        st.session_state.messages = []
                        st.session_state.waiting_for_response = False
                        st.session_state.pending_ai_message_id = None
                        _refresh_threads()
                        st.rerun()
                    except SessionExpiredError:
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create thread: {e}")

        st.divider()

        # ── Thread list ──────────────────────────────────────────────────
        _refresh_threads()

        if not st.session_state.threads:
            st.caption("No threads yet. Create one above.")
        else:
            for thread in st.session_state.threads:
                tid = thread["id"]
                label = thread["title"]
                is_active = tid == st.session_state.current_thread_id

                if is_active:
                    st.markdown(f"**▸ {label}**")
                else:
                    if st.button(label, key=f"thread_{tid}", use_container_width=True):
                        st.session_state.current_thread_id = tid
                        st.session_state.messages = []
                        st.session_state.waiting_for_response = False
                        st.session_state.pending_ai_message_id = None
                        st.rerun()

        st.divider()

        # ── Thread actions ───────────────────────────────────────────────
        if st.session_state.current_thread_id:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Share", use_container_width=True, key="share_btn"):
                    _handle_share()
            with col2:
                if st.button("Clear Chat", use_container_width=True, key="clear_btn"):
                    _handle_clear()

        st.divider()

        # ── Logout ───────────────────────────────────────────────────────
        if st.button("Logout", use_container_width=True, key="logout_btn"):
            clear_auth_state()
            st.rerun()


def _refresh_threads():
    """Fetch threads from backend."""
    try:
        st.session_state.threads = get_threads()
    except SessionExpiredError:
        st.rerun()
    except Exception:
        st.session_state.threads = []


def _handle_share():
    try:
        share = create_share(st.session_state.current_thread_id)
        uid = share["uid"]
        st.toast(f"Share link created! UID: {uid}", icon="🔗")
    except SessionExpiredError:
        st.rerun()
    except Exception as e:
        st.error(f"Failed to create share: {e}")


def _handle_clear():
    try:
        clear_messages(st.session_state.current_thread_id)
        st.session_state.messages = []
        st.session_state.waiting_for_response = False
        st.session_state.pending_ai_message_id = None
        st.rerun()
    except SessionExpiredError:
        st.rerun()
    except Exception as e:
        st.error(f"Failed to clear messages: {e}")

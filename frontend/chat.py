import streamlit as st
from api_client import get_messages, send_message
from config import POLL_INTERVAL_SECONDS


def render_chat():
    """Render the chat interface with message display, input, and polling."""
    thread_id = st.session_state.current_thread_id
    if not thread_id:
        return

    # Load messages on first visit to this thread
    if not st.session_state.messages:
        _load_messages(thread_id)

    # Display messages
    for msg in st.session_state.messages:
        role = "assistant" if msg.get("is_bot") else "user"
        content = msg.get("content", "")
        if role == "assistant" and not content:
            continue  # Skip empty AI placeholders in display
        with st.chat_message(role):
            st.markdown(content)

    # Show analyzing status while waiting
    if st.session_state.waiting_for_response:
        with st.chat_message("assistant"):
            st.status("Analyzing...", state="running")
        poll_for_response()

    # Chat input
    if prompt := st.chat_input("Ask a financial question..."):
        _handle_send(thread_id, prompt)


def _load_messages(thread_id: int):
    """Load messages from backend for the current thread."""
    try:
        msgs = get_messages(thread_id)
        st.session_state.messages = [
            {"id": m["id"], "content": m["content"], "is_bot": m["is_bot"]}
            for m in msgs
        ]
    except Exception:
        st.session_state.messages = []


def _handle_send(thread_id: int, content: str):
    """Send a message and set up polling."""
    try:
        resp = send_message(thread_id, content)
        data = resp.get("data", [])

        # Append user message
        if len(data) >= 1:
            user_msg = data[0]
            st.session_state.messages.append({
                "id": user_msg["id"],
                "content": user_msg["content"],
                "is_bot": False,
            })

        # Track AI message for polling
        if len(data) >= 2:
            ai_msg = data[1]
            st.session_state.pending_ai_message_id = ai_msg["id"]
            # Add placeholder — will be filled by polling
            st.session_state.messages.append({
                "id": ai_msg["id"],
                "content": "",
                "is_bot": True,
            })

        st.session_state.waiting_for_response = True
        st.rerun()

    except Exception as e:
        st.error(f"Failed to send message: {e}")


@st.fragment(run_every=POLL_INTERVAL_SECONDS)
def poll_for_response():
    """Poll backend for the AI response."""
    if not st.session_state.waiting_for_response:
        return

    thread_id = st.session_state.current_thread_id
    if not thread_id:
        return

    try:
        msgs = get_messages(thread_id)
    except Exception:
        return

    pending_id = st.session_state.pending_ai_message_id
    if not pending_id:
        return

    # Find the pending AI message in the fresh data
    for m in msgs:
        if m["id"] == pending_id and m.get("content"):
            # Update the placeholder in session state
            for i, local_msg in enumerate(st.session_state.messages):
                if local_msg["id"] == pending_id:
                    st.session_state.messages[i]["content"] = m["content"]
                    break

            st.session_state.waiting_for_response = False
            st.session_state.pending_ai_message_id = None
            st.rerun()
            return

import streamlit as st
import requests
from api_client import request_otp, verify_otp
from config import APP_TITLE


def render_login():
    """Render the two-step OTP login flow."""
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown(
            '<div class="login-card">', unsafe_allow_html=True
        )
        st.markdown(f"## {APP_TITLE}")
        st.markdown("Sign in with your email to continue.")
        st.divider()

        if st.session_state.auth_step == "email":
            _render_email_step()
        else:
            _render_otp_step()

        if st.session_state.error_message:
            st.error(st.session_state.error_message)

        st.markdown("</div>", unsafe_allow_html=True)


def _render_email_step():
    with st.form("email_form"):
        email = st.text_input("Email address", placeholder="you@company.com")
        submitted = st.form_submit_button("Send OTP", use_container_width=True)

    if submitted and email:
        try:
            request_otp(email.strip())
            st.session_state.auth_email = email.strip()
            st.session_state.auth_step = "otp"
            st.session_state.error_message = None
            st.rerun()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                st.session_state.error_message = "No account found for this email."
            else:
                st.session_state.error_message = "Failed to send OTP. Please try again."


def _render_otp_step():
    st.caption(f"OTP sent to **{st.session_state.auth_email}**")

    with st.form("otp_form"):
        otp = st.text_input("Enter OTP", max_chars=6, placeholder="123456")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Verify", use_container_width=True)
        with col2:
            back = st.form_submit_button("Back", use_container_width=True)

    if back:
        st.session_state.auth_step = "email"
        st.session_state.error_message = None
        st.rerun()

    if submitted and otp:
        try:
            data = verify_otp(st.session_state.auth_email, otp.strip())
            st.session_state.token = data["access_token"]
            st.session_state.user_id = data["user_id"]
            st.session_state.email = data["email"]
            st.session_state.name = data.get("name", data["email"])
            st.session_state.is_admin = data.get("is_admin", False)
            st.session_state.current_thread_id = data.get("default_thread_id")
            st.session_state.error_message = None
            st.rerun()
        except requests.HTTPError:
            st.session_state.error_message = "Invalid or expired OTP."

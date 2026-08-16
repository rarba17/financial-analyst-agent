import requests
import streamlit as st
from config import (
    REQUEST_OTP_URL,
    VERIFY_OTP_URL,
    THREADS_URL,
    MESSAGES_URL,
    SHARE_URL,
)
from state import clear_auth_state


def _headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


class SessionExpiredError(Exception):
    """Raised when the backend returns 401."""
    pass


def _handle_response(resp: requests.Response) -> dict | list | None:
    """Handle response, raising SessionExpiredError on 401."""
    if resp.status_code == 401:
        clear_auth_state()
        raise SessionExpiredError("Session expired. Please log in again.")
    resp.raise_for_status()
    if resp.status_code == 204:
        return None
    return resp.json()


# ── Auth ─────────────────────────────────────────────────────────────────────


def request_otp(email: str) -> dict:
    resp = requests.post(REQUEST_OTP_URL, json={"email": email}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def verify_otp(email: str, otp: str) -> dict:
    resp = requests.post(
        VERIFY_OTP_URL, json={"email": email, "otp": otp}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


# ── Threads ──────────────────────────────────────────────────────────────────


def create_thread(title: str) -> dict:
    resp = requests.post(
        THREADS_URL, json={"title": title}, headers=_headers(), timeout=10
    )
    return _handle_response(resp)


def get_threads() -> list:
    resp = requests.get(THREADS_URL, headers=_headers(), timeout=10)
    return _handle_response(resp)


# ── Messages ─────────────────────────────────────────────────────────────────


def send_message(thread_id: int, content: str) -> dict:
    resp = requests.post(
        MESSAGES_URL,
        json={"thread_id": thread_id, "content": content},
        headers=_headers(),
        timeout=30,
    )
    return _handle_response(resp)


def get_messages(thread_id: int) -> list:
    resp = requests.get(
        f"{THREADS_URL}/{thread_id}/messages", headers=_headers(), timeout=10
    )
    return _handle_response(resp)


def clear_messages(thread_id: int) -> None:
    resp = requests.delete(
        f"{THREADS_URL}/{thread_id}/messages", headers=_headers(), timeout=10
    )
    _handle_response(resp)


# ── Share ────────────────────────────────────────────────────────────────────


def create_share(thread_id: int) -> dict:
    resp = requests.post(
        f"{SHARE_URL}/", json={"thread_id": thread_id}, headers=_headers(), timeout=10
    )
    return _handle_response(resp)


def get_share_messages(share_uid: str) -> list:
    resp = requests.get(
        f"{SHARE_URL}/{share_uid}/messages", headers=_headers(), timeout=10
    )
    return _handle_response(resp)


def continue_share(share_uid: str) -> dict:
    resp = requests.get(
        f"{SHARE_URL}/{share_uid}/continue", headers=_headers(), timeout=10
    )
    return _handle_response(resp)

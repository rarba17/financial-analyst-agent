import streamlit as st

CUSTOM_CSS = """
<style>
/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #1A1A2E;
    border-right: 1px solid #2A2A4A;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #E0E0E0;
}

/* Chat message styling */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    margin-bottom: 8px;
    padding: 12px 16px;
}

/* User messages */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: #1E3A5F;
}

/* Assistant messages */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: #16213E;
}

/* Table styling inside chat */
[data-testid="stChatMessage"] table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 0.85em;
}

[data-testid="stChatMessage"] th {
    background-color: #2A2A4A;
    color: #E0E0E0;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 2px solid #4A90D9;
}

[data-testid="stChatMessage"] td {
    padding: 6px 12px;
    border-bottom: 1px solid #2A2A4A;
    color: #D0D0D0;
}

[data-testid="stChatMessage"] tr:hover td {
    background-color: rgba(74, 144, 217, 0.1);
}

/* Thread buttons in sidebar */
.thread-btn button {
    width: 100%;
    text-align: left;
    border: none;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 0;
}

/* Login card */
.login-card {
    background-color: #16213E;
    border-radius: 16px;
    padding: 40px;
    border: 1px solid #2A2A4A;
    margin-top: 60px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 80px 20px;
    color: #888;
}

/* Smooth transitions */
[data-testid="stChatMessage"] {
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
"""


def apply_styles():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

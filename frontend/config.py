API_BASE_URL = "http://localhost:8000"
API_V1 = f"{API_BASE_URL}/api/v1"

# Auth endpoints
REQUEST_OTP_URL = f"{API_V1}/auth/request-otp"
VERIFY_OTP_URL = f"{API_V1}/auth/verify-otp"

# Chat endpoints
THREADS_URL = f"{API_V1}/chat/threads"
MESSAGES_URL = f"{API_V1}/chat/messages"

# Share endpoints
SHARE_URL = f"{API_V1}/share"

# Polling
POLL_INTERVAL_SECONDS = 1.5
POLL_TIMEOUT_SECONDS = 120

# UI
APP_TITLE = "GCPL Financial Analyst"
APP_SUBTITLE = "AI-powered financial analysis for business leaders"

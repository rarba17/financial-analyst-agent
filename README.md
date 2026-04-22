# CCPL Financial Intelligence Agent

An agentic AI backend that acts as a real-time financial analyst for CCPL (a major FMCG consumer products company). Business users can ask natural-language questions about P&L data and receive analyst-quality insights — no SQL or data science knowledge required.

---

## What It Does

The system lets users query financial data conversationally:

```
User:  "What was India's EBITDA in December 2024?"
Agent: → Selects the right tool → Executes SQL against the financial database
       → Returns formatted report with YoY comparison, margin calculation, and follow-up suggestions
```

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI · Python 3.12 |
| Agent | LangChain · GPT-4o / Azure OpenAI |
| Database | PostgreSQL (SQLAlchemy + psycopg) |
| Financial Data | SQLite (`flattened.db`) |
| Auth | OTP via Azure Communication Services + JWT |
| Real-time | Redis pub/sub → WebSocket |
| Migrations | Alembic |

---

## Project Structure

```
.
├── main.py                  # FastAPI app entry point
├── api/v1/
│   ├── auth.py              # OTP + JWT authentication routes
│   ├── chat.py              # Thread/message management routes
│   └── share.py             # Conversation sharing routes
├── agent/
│   ├── standalone_agent.py  # GCPLFinancialAgent class
│   └── cli.py               # Interactive CLI interface
├── tools/
│   ├── basic_metrics.py     # query_basic_metrics tool
│   ├── time_series.py       # analyze_time_series tool
│   ├── rankings_extrema.py  # find_rankings_extrema tool
│   ├── region_comparison.py # compare_regions tool
│   └── driver_analysis.py   # analyze_drivers tool
├── services/
│   ├── agent_service.py     # Agent invocation service
│   ├── chat_status_service.py
│   ├── message_service.py
│   ├── redis_service.py
│   ├── thread_service.py
│   ├── user_service.py
│   └── ws_service.py        # WebSocket connection manager
├── auth/
│   └── otp_store.py
├── core/
│   ├── config.py            # Pydantic settings (loads .env)
│   ├── database.py
│   └── security.py          # JWT + password hashing
├── db/
│   └── session.py
├── models/                  # SQLAlchemy ORM models
├── schemas/                 # Pydantic request/response schemas
├── migrations/              # Alembic migrations
├── Data Files/
│   ├── flattened.db         # SQLite financial database
│   └── ccpl_finpac_metadata_v3.json
└── query_optimizer.py       # Optional LLM-based query enhancement
```

---

## Agent Tools

The agent selects from 5 specialized tools based on query type:

| Tool | Use Case | Example |
|---|---|---|
| `query_basic_metrics` | Single value retrieval | "What was India's Net Sales in Dec 2024?" |
| `analyze_time_series` | MoM/YoY trends, rolling averages | "What's the MoM change in EBITDA from Feb to Mar 2025?" |
| `find_rankings_extrema` | Peaks, valleys, best/worst periods | "Which month had peak EBITDA for India?" |
| `compare_regions` | Cross-region comparisons | "Rank India, Indonesia, and GAUM by Net Sales in Mar 2025" |
| `analyze_drivers` | Waterfall analysis, driver attribution | "What are the top drivers of EBITDA change?" |

---

## API Endpoints

### Auth (`/api/v1/auth`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/request-otp` | Send OTP to registered email |
| `POST` | `/verify-otp` | Verify OTP → returns JWT + default thread ID |
| `POST` | `/users` | Create user (admin only) |
| `GET` | `/users` | List users (admin only) |
| `DELETE` | `/users/{user_id}` | Delete user (admin only) |

### Chat (`/api/v1/chat`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/threads` | Create conversation thread |
| `GET` | `/threads` | List user's threads |
| `POST` | `/messages` | Send message → triggers agent |
| `GET` | `/threads/{id}/messages` | Get thread history |
| `DELETE` | `/threads/{id}/messages` | Clear thread messages |

### Share (`/api/v1/share`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Share a thread → returns share UID |
| `GET` | `/{uid}/messages` | View shared conversation |
| `GET` | `/{uid}/continue` | Fork shared thread into new thread |

### WebSocket

```
WS /ws/interactions/{message_id}
```
Streams agent status and response chunks in real time via Redis pub/sub.

---

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis
- Azure Communication Services account (for OTP emails)
- Azure OpenAI or OpenAI API key

### Install

```bash
pip install poetry
poetry install
```

Or with pip:

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# App
PROJECT_NAME=CCPL Financial Agent
ENVIRONMENT=dev
PORT=8000
WORKERS=2

# PostgreSQL
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_db

# JWT
SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_SECRET_KEY=your_refresh_secret
ACCESS_TOKEN_EXPIRE_DAYS=7

# Azure Communication (OTP emails)
AZURE_COMMUNICATION_CONNECTION_STRING=your_connection_string
AZURE_EMAIL_SENDER=noreply@yourdomain.com

# Admin user (auto-created on startup)
ADMIN_EMAIL=admin@example.com
ADMIN_OTP=your_admin_otp

# Azure OpenAI
USE_AZURE_OPENAI=true
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
LLM_MODEL_NAME=gpt-4o

# OpenAI (fallback)
OPENAI_API_KEY=your_openai_key

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_CHANNEL=ccpl_broadcast_channel

# LangChain (optional tracing)
LANGCHAIN_API_KEY=your_langsmith_key
LANGSMITH_TRACING=false
LANGCHAIN_PROJECT=ccpl-financial-agent

# Data files
DATABASE_PATH=Data Files/flattened.db
METADATA_PATH=Data Files/ccpl_finpac_metadata_v3.json
SQL_PROMPT_PATH=Data Files/Company.md
BUSINESS_PROMPT_PATH=Data Files/1.md
```

### Database Migration

```bash
alembic upgrade head
```

### Run the Server

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at `http://localhost:8000/api/v1/openapi.json`.

---

## CLI Usage

Run the agent interactively from the terminal without starting the full server:

```bash
python -m agent.cli
```

Available commands in the CLI:

```
help       Show help
examples   Show example queries
history    View conversation history
clear      Clear conversation history
exit       Quit
```

---

## Docker

```bash
docker build -t ccpl-agent .
docker run -p 8000:8000 --env-file .env ccpl-agent
```

---

## Authentication Flow

1. Admin creates user accounts via `POST /api/v1/auth/users`
2. User calls `POST /api/v1/auth/request-otp` with their email
3. OTP is sent via Azure Communication Services (valid for 2 minutes)
4. User calls `POST /api/v1/auth/verify-otp` to get a JWT
5. All subsequent requests use `Authorization: Bearer <token>`

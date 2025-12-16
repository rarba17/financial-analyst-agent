FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY app app/
COPY alembic.ini .
COPY alembic alembic/

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Use environment variable for port with default value
ENV PORT=8000
EXPOSE ${PORT}

# Command to run the application
CMD ["sh", "-c", "alembic upgrade head && poetry run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
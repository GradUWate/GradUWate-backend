FROM python:3.11-slim

# Install Poetry
ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VIRTUALENVS_CREATE=false
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Copy only dependency files first for better caching
COPY pyproject.toml ./
COPY poetry.lock ./

# Install deps (only main deps for image size; add --with dev if needed)
RUN poetry install --no-interaction --no-ansi --no-root

# Now copy the application code
COPY app app
COPY .env .env

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--reload"]

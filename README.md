# Course Graph API (FastAPI + Poetry)

Base FastAPI scaffold managed by **Poetry**. No business logic yet.

---

## 🧩 Prerequisites

- **Python** 3.11 or 3.12
- **Poetry** → [Install Guide](https://python-poetry.org/docs/#installation)

---

## 🚀 Setup

```bash
# 1) Install dependencies (with dev tools)
poetry install --with dev

# 2) Copy environment file
cp .env.example .env

# 3) Run the API (dev)
poetry run uvicorn app.main:app --reload --port 8000
# open http://localhost:8000/docs
```

Or use the Makefile shortcuts:

```bash
make dev     # poetry install --with dev
make run     # poetry run uvicorn app.main:app --reload --port 8000
make test    # pytest
make lint    # ruff
make type    # mypy
make fmt     # ruff --fix
```

---

## 🧱 Project Structure

- `app/main.py`: FastAPI app, CORS, health route
- `app/api/v1/endpoints/`: add routers here (e.g., courses.py later)
- `app/db/`: DB engine/session/models (placeholder)
- `app/schemas/`: Pydantic schemas
- `app/services/`: business logic
- `app/tasks/`: schedulers/cron
- `tests/`: pytest tests

---

## 🐳 Docker (Poetry inside image)

```bash
docker compose up --build
# open http://localhost:8000/docs
```

---

## 📦 Export Pinned Requirements (optional)

```bash
make export-reqs
# generates requirements.txt and requirements-dev.txt from poetry.lock
```

---

## 🧪 Notes

- Swagger UI → http://localhost:8000/docs
- ReDoc → http://localhost:8000/redoc
- Health check → GET /health

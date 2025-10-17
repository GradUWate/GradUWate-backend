
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

app = FastAPI(
    title="GradUWate API",
    version="0.1.0",
    description=(
        "Backend for GradUWate.\n\n"
        "Prototype 1 target: base requirements, visual map, swagger, and scaffolding."
    ),
    contact={"name": "Team SE 390"},
    openapi_tags=[
        {"name": "health", "description": "Service health & metadata"},
        {"name": "courses", "description": "Course graph endpoints (placeholder)"},
        {"name": "scraper", "description": "Scraper/cron (placeholder)"},
    ],
)

configure_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "course-graph-api",
        "env": settings.ENV,
        "version": "0.1.0",
    }

@app.get("/", include_in_schema=False)
def root():
    return {"docs": "/docs", "redoc": "/redoc"}

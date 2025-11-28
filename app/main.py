
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints.course import router as courses_router

from app.core.config import settings
from app.core.logging import configure_logging

from app.db.neo4j.graph_adapter import init_neo4j, close_neo4j
from app.db.bootstrap import bootstrap_from_parsed_records
from app.db.postgres.session import engine, async_session, Base
from .parsing import fetch_courses

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
    allow_origins=settings.cors_origins,
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

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    driver = await init_neo4j()

    async with async_session() as db:
        await bootstrap_from_parsed_records(db, fetch_courses())

@app.on_event("shutdown")
async def shutdown():
    await close_neo4j()

@app.get("/", include_in_schema=False)
def root():
    return {"docs": "/docs", "redoc": "/redoc"}

app.include_router(courses_router)

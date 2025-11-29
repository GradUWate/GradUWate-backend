import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints.course import router as courses_router

from app.core.config import settings
from app.core.logging import configure_logging

from app.db.neo4j.graph_adapter import init_neo4j, close_neo4j
from app.db.bootstrap import bootstrap_from_parsed_records
from app.db.postgres.session import engine, async_session, Base
from app.parsing import fetch_courses

app = FastAPI(
    title="GradUWate API",
    version="0.1.0",
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
    return {"status": "ok", "service": "course-graph-api"}

@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "message": "Backend is running"}

# --- THE FIX IS HERE ---
async def run_data_loading():
    """
    Runs the heavy data scraping and DB insertion in the background.
    """
    print("⏳ BACKGROUND TASK: Starting data scraping...")
    
    # 1. Run the blocking 'fetch_courses' in a separate thread so it doesn't freeze the server
    courses_data = await asyncio.to_thread(fetch_courses)
    print(f"✅ BACKGROUND TASK: Scraped {len(courses_data)} courses. Starting DB insert...")

    # 2. Insert into DB (this part is already async)
    async with async_session() as db:
        await bootstrap_from_parsed_records(db, courses_data)
    
    print("🎉 BACKGROUND TASK: Data loading complete!")

@app.on_event("startup")
async def startup():
    # 1. Create Postgres Tables (Fast)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Connect to Neo4j (Fast, unless firewall issues)
    await init_neo4j()

    # 3. START DATA LOADING IN BACKGROUND
    # This creates a task and immediately lets the server continue to start.
    asyncio.create_task(run_data_loading())

@app.on_event("shutdown")
async def shutdown():
    await close_neo4j()

app.include_router(courses_router)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session
from db.graph import get_neo4j, upsert_course_node, merge_edge
from .. import crud
from app.parsing import extract_course_tokens, seasons_from_text
from schemas.parse import RowIn

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/row")
async def ingest_row(body: RowIn, db: AsyncSession = Depends(get_session)):
    # 1) Upsert course (Postgres)
    await crud.upsert_course(
        db,
        id=body.id,
        code=body.code,
        title=body.title,
        description=body.description,
        level=None,
    )
    # 2) Terms
    seasons = seasons_from_text(body.terms_offered)
    await crud.add_term_rules(db, course_id=body.id, seasons=seasons)
    await db.commit()

    # 3) Mirror node to Neo4j
    driver = get_neo4j()
    await upsert_course_node(driver, id=body.id, code=body.code, title=body.title, level=None)

    # Relation edges can be added here if you provide code→id mapping:
    for prereq_code in extract_course_tokens(body.prereq_text):
        from_id = crud.get_course_by_code(db, prereq_code) # lookup
        await merge_edge(driver, from_id=from_id, to_id=body.id, kind="PREREQ_OF")

    return {"ok": True, "course_id": body.id, "terms": seasons,
            "parsed": {"prereq": extract_course_tokens(body.prereq_text),
                       "coreq": extract_course_tokens(body.coreq_text),
                       "successors": extract_course_tokens(body.successors)}}
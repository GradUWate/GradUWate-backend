from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.postgres.session import get_session
from app.db.postgres.crud import get_course_by_code
from app.db.neo4j.graph_adapter import init_neo4j, get_neo4j, collect_graph_for_id
from neo4j import AsyncGraphDatabase, AsyncDriver

router = APIRouter(prefix="/api/v1", tags=["courses"])


def _normalize_code_to_store(code: str) -> str:
    return " ".join(code.replace("-", " ").strip().upper().split())


def _code_to_id(code: str) -> str:
    # "CS 135" -> "CS-135"
    parts = _normalize_code_to_store(code).split()
    return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else code.replace(" ", "-")


@router.get("/courses/{code}")
async def get_course(code: str, db: AsyncSession = Depends(get_session)):
    norm = _normalize_code_to_store(code)
    course = await get_course_by_code(db, norm)
    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    # fetch constraints for this course (prereq / antireq)
    sql = text(
        "SELECT kind, target_course_id, group_id FROM course_constraint WHERE course_id = :course_id"
    )
    res = await db.execute(sql, {"course_id": course.id})
    rows = res.mappings().all()

    prereqs: List[Dict[str, Any]] = []
    antireqs: List[Dict[str, Any]] = []
    for r in rows:
        tgt = r["target_course_id"]
        entry = {"id": tgt, "code": tgt.replace("-", " ")}
        if r["kind"] == "PREREQ":
            entry["group_id"] = r["group_id"]
            prereqs.append(entry)
        elif r["kind"] == "ANTIREQ":
            antireqs.append(entry)

    return {
        "id": course.id,
        "code": course.code,
        "title": course.title,
        "description": course.description,
        "level": course.level,
        "prereqs": prereqs,
        "antireqs": antireqs,
    }



@router.get("/courses/{code}/backpath")
async def get_backpath(code: str):
    """Courses that lead to this course (prereq graph)"""
    try:
        cid = _code_to_id(code)
        driver = get_neo4j()
        print("DRIVER"  , driver._check_state())
        if not driver:
            raise Exception("neo4j not available", driver)
        graph = await collect_graph_for_id(driver, cid, rel_type="REQUIRES", depth=6)
        return graph

    except Exception as e:
        print(f"Error in get_backpath: {e}")
        raise HTTPException(status_code=503, detail="neo4j not available")



@router.get("/courses/{code}/frontpath")
async def get_frontpath(code: str):
    """Courses that this course leads to (successor graph)"""
    cid = _code_to_id(code)
    driver = get_neo4j()
    if not driver:
        raise HTTPException(status_code=503, detail="neo4j not available")
    graph = await collect_graph_for_id(driver, cid, rel_type="UNLOCKS", depth=6)
    return graph


# Hard-coded test plans (temporary)
_PLANS = {
    "SE major": ["CS 135", "CS 136", "CS 246", "MATH 135"],
    "AI specialization": ["CS 486", "CS 484", "MATH 239"],
    "MTE minor": ["MTE 121", "MTE 122"]
}


@router.post("/courses/by-plans")
async def courses_by_plans(plans: List[str]):
    """
    Input: JSON array of plan names.
    Returns combined prerequisite graphs for all selected plans (aggregated).
    """
    # collect requested plan course list (flat, unique)
    selected_codes = []
    for p in plans:
        selected_codes.extend(_PLANS.get(p, []))
    selected_codes = sorted(set(selected_codes))
    if not selected_codes:
        return {"nodes": [], "links": [], "plans": plans, "requested_codes": []}

    ids = [_code_to_id(c) for c in selected_codes]
    driver = get_neo4j()
    if not driver:
        raise HTTPException(status_code=503, detail="neo4j not available")

    agg_nodes: Dict[str, Dict] = {}
    agg_links: List[Dict] = []
    for cid in ids:
        sub = await _collect_graph_for_id(driver, cid, rel_type="REQUIRES", depth=5)
        for n in sub["nodes"]:
            agg_nodes[n["id"]] = n
        agg_links.extend(sub["links"])

    # dedupe links
    seen = set()
    uniq_links = []
    for l in agg_links:
        key = (l.get("start"), l.get("end"), l.get("type"), l.get("group_id"))
        if key not in seen:
            seen.add(key)
            uniq_links.append(l)

    return {"nodes": list(agg_nodes.values()), "links": uniq_links, "plans": plans, "requested_codes": selected_codes}
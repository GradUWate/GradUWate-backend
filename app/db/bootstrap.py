from typing import Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from .requirements_parsing import extract_constraints
from .postgres.crud import upsert_course, add_constraints   # uses your existing CRUD + the new add_constraints
from .neo4j.graph_adapter import get_neo4j, upsert_course_node, merge_prereq_edge, merge_antireq_edge

def _course_pk(subject: str, number: str) -> str:
    return f"{subject}-{number}"

def _id_from_code(code: str) -> str:
    # "CS 135" -> "CS-135"
    subj, num = code.split()
    return f"{subj}-{num}"

def _normalize(rec: Dict) -> Dict:
    subject = rec["subjectCode"]
    number  = rec["catalogNumber"]
    return {
        "id": _course_pk(subject, number),
        "code": f"{subject} {number}",
        "subject": subject,
        "number": number,
        "title": rec.get("title") or "",
        "description": rec.get("description"),
        "requirements": rec.get("requirementsDescription") or "",
    }

def _rows_for_constraints(course_id: str, req: str) -> List[Tuple[str, str, str, str|None]]:
    """
    Generate rows for course_constraint:
      (course_id, kind, target_course_id, group_id)
    """
    out: List[Tuple[str, str, str, str|None]] = []
    parsed = extract_constraints(req)
    # prereq groups
    for gi, group in enumerate(parsed["prereq_groups"], start=1):
        gid = f"{course_id}#g{gi}"
        for code in group:
            out.append((course_id, "PREREQ", _id_from_code(code), gid))
    # antireqs
    for code in parsed["antireqs"]:
        out.append((course_id, "ANTIREQ", _id_from_code(code), None))
    return out

async def bootstrap_from_parsed_records(db: AsyncSession, parsed: List[Dict]) -> Dict:
    """
    Accepts paser results
    Writes courses, constraints, and graph edges
    """
    records = [_normalize(r) for r in parsed]

    # upsert courses Postgres
    for r in records:
        await upsert_course(
            db,
            id=r["id"],
            code=r["code"],
            title=r["title"],
            description=r["description"],
            level= int(r["code"][-3] + "00"),
        )

    # constraints → Postgres
    all_rows: List[Tuple[str, str, str, str|None]] = []
    for r in records:
        all_rows.extend(_rows_for_constraints(r["id"], r["requirements"]))
    if all_rows:
        await add_constraints(db, all_rows)

    # graph nodes + edges
    driver = get_neo4j()
    try:
        # nodes
        for r in records:
            await upsert_course_node(driver, id=r["id"], code=r["code"], title=r["title"], level=None)

        # edges
        for r in records:
            course_id = r["id"]
            parsed_req = extract_constraints(r["requirements"])
            # prereq groups
            for gi, group in enumerate(parsed_req["prereq_groups"], start=1):
                gid = f"{course_id}#g{gi}"
                for code in group:
                    await merge_prereq_edge(driver, to_id=course_id, from_id=_id_from_code(code), group_id=gid)
            # antireqs (store both directions for practical lookups)
            for code in parsed_req["antireqs"]:
                other = _id_from_code(code)
                await merge_antireq_edge(driver, a_id=course_id, b_id=other)
                await merge_antireq_edge(driver, a_id=other, b_id=course_id)
    finally:
        if hasattr(driver, "close"):
            await driver.close() if callable(getattr(driver, "close")) else None

    return {
        "inserted": len(records),
        "constraints_rows": len(all_rows),
    }
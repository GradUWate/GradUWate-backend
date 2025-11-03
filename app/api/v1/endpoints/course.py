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
# ...existing code...
# Detailed plan definition for Software Engineering (test/hard-coded)
_SE_PLAN = {
    "name": "Software Engineering (BSE)",
    "total_units_required": 21.5,
    "required_courses": [
        # 1A
        "CS 137", "CHE 102", "MATH 115", "MATH 117", "MATH 135", "SE 101",
        # 1B
        "CS 138", "ECE 124", "ECE 140", "ECE 192", "MATH 119", "SE 102",
        # 2A
        "CS 241", "ECE 222", "SE 201", "SE 212", "STAT 206",
        # 2B
        "CS 240", "CS 247", "CS 348", "MATH 239", "SE 202",
        # 3A
        "CS 341", "MATH 213", "SE 301", "SE 350", "SE 464", "SE 465",
        # 3B (primary required courses)
        "CS 343", "ECE 358", "SE 302", "SE 380", "SE 463",
        # 4A/4B project & seminar placeholders
        "SE 401", "SE 402", "GENE 403", "GENE 404", "SE 490", "SE 491",
    ],
    # Complementary Studies (CSE) lists — placeholders for List A and List C (fill in as needed)
    "complementary_lists": {
        "A": [
            # Example placeholders (replace with actual List A course codes)
            "COMMST 100", "ENGL 109"
        ],
        "C": [
            # Example placeholders (replace with actual List C course codes)
            "PHIL 224", "HUMN 101"
        ],
        "choose": {"A": 1, "C": 1}
    },
    # Undergraduate communication requirement options (choose 1)
    "communication_requirement": {
        "choose": 1,
        "courses": [
            "COMMST 100", "COMMST 223", "EMLS101R", "EMLS102R", "EMLS129R",
            "ENGL109", "ENGL119", "ENGL129R", "ENGL209", "ENGL210E"
        ]
    },
    # Natural Science list (choose 3 lecture courses; labs paired where applicable)
    "natural_science": {
        "choose": 3,
        "courses": [
            "AMATH382","BIOL110","BIOL130","BIOL130L","BIOL150","BIOL165","BIOL211",
            "BIOL220","BIOL239","BIOL240","BIOL240L","BIOL241","BIOL273","BIOL280",
            "BIOL365","BIOL373","BIOL373L","BIOL376","BIOL382","BIOL469","BIOL476",
            "BIOL489","CHE 161","CHEM123","CHEM123L","CHEM209","CHEM237","CHEM237L",
            "CHEM254","CHEM262","CHEM262L","CHEM266","CHEM356","CS482","EARTH121",
            "EARTH122","EARTH123","EARTH221","EARTH270","EARTH281","ECE106","ECE231",
            "ECE305","ECE403","ECE404","ENVE275","ENVS200","NE222","PHYS122","PHYS124",
            "PHYS175","PHYS233","PHYS234","PHYS263","PHYS275","PHYS280","PHYS334","PHYS335",
            "PHYS375","PHYS380","PHYS468","PSYCH207","PSYCH261","PSYCH306","PSYCH307",
            "SCI200","SCI201","SCI238","SCI250"
        ]
    },
    # Technical Electives lists (min 4 total; at least one from List1/List2 depending on rules)
    "technical_electives": {
        "min_required": 4,
        "list1": [
            "AMATH242","AMATH449","CS360","CS365","CS370","CS371","CS442","CS444",
            "CS448","CS450","CS451","CS452","CS453","CS454","CS457","CS459","CS462",
            "CS466","CS479","CS480","CS484","CS485","CS486","CS487","CS488","CS489"
        ],
        "list2": [
            "ECE313","ECE320","ECE327","ECE340","ECE405A","ECE405B","ECE405C","ECE405D",
            "ECE409","ECE416","ECE417","ECE423","ECE454","ECE455","ECE457A","ECE457B",
            "ECE457C","ECE458","ECE459","ECE481","ECE486","ECE488","ECE493","ECE495"
        ],
        "list3": [
            "BIOL487","CO331","CO342","CO351","CO353","CO367","CO456","CO481","CO485",
            "CO487","CS467","MSE343","MSE446","MSE543","MTE544","MTE546","PHYS467",
            "SE498","STAT440","STAT441","STAT442","STAT444","SYDE533","SYDE543","SYDE548",
            "SYDE552","SYDE556","SYDE575"
        ]
    },
    "sustainability_options": [
        "BIOL489","EARTH270","ENBUS102","ENBUS211","ENGL248","ENVS105","ENVS200","ENVS205",
        "ENVS220","ERS215","ERS225","ERS253","ERS270","ERS294","ERS310","ERS316","ERS320",
        "ERS328","ERS361","ERS370","ERS372","ERS404","GEOG203","GEOG207","GEOG225","GEOG361",
        "GEOG459","PACS310","PHIL224","PLAN451","PSCI432","RCS285","SCI200","SCI201","THPERF374"
    ],
    "co_op": {
        "pd_courses": ["PD10","PD11","PD19","PD20","PDX"],  # PDX placeholder for the 5th PD
        "work_terms_required": 5
    },
    "notes": [
        "Some courses may be taken out of sequence per program rules.",
        "Technical electives may not be taken before 3A term.",
        "Complementary studies lists A/C need to be filled with official course codes."
    ]
}

# top-level plans mapping used by endpoints
_PLANS = {
    "SE major": _SE_PLAN,
    "Software Engineering": _SE_PLAN,
    "AI specialization": {"name": "AI specialization", "required_courses": ["CS 486", "CS 484", "MATH 239"]},
    "MTE minor": {"name": "MTE minor", "required_courses": ["MTE 121", "MTE 122"]},
}

def _expand_plan_to_codes(plan_def: dict) -> List[str]:
    """Return a flattened list of course codes represented by a plan definition.
    For elective groups we include all candidate codes so the graph can show possible dependencies.
    """
    codes = set()
    if not plan_def:
        return []
    # required courses
    for c in plan_def.get("required_courses", []):
        codes.add(_normalize_code_to_store(c))
    # communication requirement
    for c in plan_def.get("communication_requirement", {}).get("courses", []):
        codes.add(_normalize_code_to_store(c))
    # complementary lists A/C
    comp = plan_def.get("complementary_lists", {})
    for lst in ("A", "C"):
        for c in comp.get(lst, []):
            codes.add(_normalize_code_to_store(c))
    # natural science candidates
    for c in plan_def.get("natural_science", {}).get("courses", []):
        codes.add(_normalize_code_to_store(c))
    # technical electives lists
    te = plan_def.get("technical_electives", {})
    for key in ("list1", "list2", "list3"):
        for c in te.get(key, []):
            codes.add(_normalize_code_to_store(c))
    # sustainability options
    for c in plan_def.get("sustainability_options", []):
        codes.add(_normalize_code_to_store(c))
    # co-op PDs (not courses used for graph usually) - skip adding
    # notes etc. ignore
    return sorted(codes)

@router.post("/courses/by-plans")
async def courses_by_plans(plans: List[str]):
    """
    Input: JSON array of plan names.
    Returns combined prerequisite graphs for all selected plans (aggregated).
    Unknown plan names are reported in `unknown_plans`.
    """
    if not plans:
        raise HTTPException(status_code=400, detail="request body must be a non-empty JSON array of plan names")

    selected_codes = []
    unknown = []
    for p in plans:
        entry = _PLANS.get(p)
        if not entry:
            unknown.append(p)
            continue
        # if entry is a dict plan definition expand otherwise treat as flat list
        if isinstance(entry, dict):
            selected_codes.extend(_expand_plan_to_codes(entry))
        elif isinstance(entry, list):
            selected_codes.extend([_normalize_code_to_store(c) for c in entry])

    selected_codes = sorted(set(selected_codes))
    if not selected_codes:
        return {"nodes": [], "links": [], "plans": plans, "requested_codes": [], "unknown_plans": unknown}

    ids = [_code_to_id(c) for c in selected_codes]
    driver = get_neo4j()
    if not driver:
        raise HTTPException(status_code=503, detail="neo4j not available")

    agg_nodes: Dict[str, Dict] = {}
    agg_links: List[Dict] = []
    for cid in ids:
        sub = await collect_graph_for_id(driver, cid, rel_type="REQUIRES", depth=6)
        for n in sub.get("nodes", []):
            agg_nodes[n["id"]] = n
        agg_links.extend(sub.get("links", []))

    # dedupe links
    seen = set()
    uniq_links = []
    for l in agg_links:
        key = (l.get("start"), l.get("end"), l.get("type"), l.get("group_id"))
        if key not in seen:
            seen.add(key)
            uniq_links.append(l)

    resp = {"nodes": list(agg_nodes.values()), "links": uniq_links, "plans": plans, "requested_codes": selected_codes}
    if unknown:
        resp["unknown_plans"] = unknown
    return resp
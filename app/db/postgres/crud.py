from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from ..models.courses import Course, CourseTermRule
from typing import Iterable, Tuple, List

async def get_course_by_code(db: AsyncSession, code: str) -> Course | None:
    q = select(Course).where(Course.code == code)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def get_all_courses(db: AsyncSession) -> List[Course] | None:
    q = select(Course)
    r = await db.execute(q)
    return r.scalars().all()

async def upsert_course(db: AsyncSession, *, id: str, code: str, title: str, description: str | None, level: int | None):
    obj = await db.get(Course, id)
    if not obj:
        obj = Course(id=id, code=code, title=title, description=description, level=level)
        db.add(obj)
    else:
        obj.code, obj.title, obj.description, obj.level = (
            code, title, description, level,
        )
    await db.flush(); return obj

async def add_term_rules(db: AsyncSession, *, course_id: str, seasons: list[str]):
    for s in seasons:
        db.add(CourseTermRule(id=course_id+":"+s, course_id=course_id, season=s))
    await db.flush()

# edges: Iterable[Tuple[course_id, kind, target_course_id, group_id]]
async def add_constraints(db: AsyncSession, edges: Iterable[Tuple[str, str, str, str | None]]):
    rows = []
    for (c, k, t, g) in edges:
        rows.append({
            "course_id": c,
            "kind": k,                      # 'PREREQ' or 'ANTIREQ'
            "target_course_id": t,
            "group_id": g or "",            # normalize None -> ''
        })
    if not rows:
        return

    sql = text("""
        INSERT INTO course_constraint (course_id, kind, target_course_id, group_id)
        VALUES (:course_id, :kind, :target_course_id, :group_id)
        ON CONFLICT (course_id, kind, target_course_id, group_id) DO NOTHING
    """)
    await db.execute(sql, rows)
    await db.commit()
import asyncio
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import settings

_driver: AsyncDriver | None = None


async def init_neo4j(max_wait_seconds: int = 30) -> None:
    """
    Connect to Neo4j and create the unique constraint. We retry until the
    Bolt server is reachable (up to max_wait_seconds).
    """
    global _driver
    if _driver is not None:
        return

    deadline = asyncio.get_event_loop().time() + max_wait_seconds
    last_err: Exception | None = None

    while asyncio.get_event_loop().time() < deadline:
        try:
            _driver = AsyncGraphDatabase.driver(
                settings.neo4j_url,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            # Test the connection and create constraint
            async with _driver.session() as s:
                await s.run(
                    "CREATE CONSTRAINT course_id IF NOT EXISTS "
                    "FOR (c:Course) REQUIRE c.id IS UNIQUE"
                )
                await s.run(
                    "CREATE INDEX course_code IF NOT EXISTS FOR (c:Course) ON (c.code)"
                )
            return
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.0)
    _driver = None


def get_neo4j() -> AsyncDriver | None:
    """Return the driver if ready; otherwise None (so callers can skip graph work)."""
    return _driver


async def close_neo4j() -> None:
    """Close the shared driver (handy for tests / graceful shutdown)."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def upsert_course_node(
    driver: AsyncDriver, *, id: str, code: str, title: str, level: int | None
):
    """
    Upsert a Course node with full properties.
    """
    cypher = """
    MERGE (c:Course {id:$id})
    SET   c.code  = $code,
          c.title = $title,
          c.level = $level
    """
    async with driver.session() as s:
        await s.run(cypher, id=id, code=code, title=title, level=level)


async def merge_prereq_edge(driver: AsyncDriver, to_id: str, from_id: str, group_id: str):
    """
    REQUIRES: (to)-[:REQUIRES {group_id}]->(from)   # 'to' requires 'from'
    UNLOCKS:  (from)-[:UNLOCKS  {group_id}]->(to)
    Ensure placeholder nodes get readable fallbacks for code/title.
    """
    cy = """
    MERGE (to:Course {id:$to_id})
      ON CREATE SET to.code = $to_id, to.title = $to_id
    MERGE (from:Course {id:$from_id})
      ON CREATE SET from.code = $from_id, from.title = $from_id

    MERGE (to)-[r:REQUIRES {group_id:$group_id}]->(from)
    MERGE (from)-[:UNLOCKS {group_id:$group_id}]->(to)
    RETURN id(r)
    """
    async with driver.session() as s:
        await s.run(cy, to_id=to_id, from_id=from_id, group_id=group_id)


async def merge_antireq_edge(driver: AsyncDriver, a_id: str, b_id: str):
    """
    ANTIREQ: (a)-[:ANTIREQ]->(b)
    Also give readable fallbacks for nodes created implicitly.
    """
    cy = """
    MERGE (a:Course {id:$a})
      ON CREATE SET a.code = $a, a.title = $a
    MERGE (b:Course {id:$b})
      ON CREATE SET b.code = $b, b.title = $b
    MERGE (a)-[:ANTIREQ]->(b)
    """
    async with driver.session() as s:
        await s.run(cy, a=a_id, b=b_id)
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


async def collect_graph_for_id(driver: AsyncDriver, id_value: str, rel_type: str = "REQUIRES", depth: int = 6):
    """
    rel_type: 'REQUIRES' (follow :REQUIRES out from node to prereqs)
              'UNLOCKS'  (follow :UNLOCKS out from node to successors)
    """
    if not driver:
        return {"nodes": [], "links": []}

    cy = f"""
    MATCH path=(c:Course {{id:$id}})-[:{rel_type}*1..{depth}]->(n)
    RETURN
      [x IN nodes(path) | {{id: x.id, code: x.code, title: x.title, level: x.level}}] AS nds,
      [r IN relationships(path) | {{start: startNode(r).id, end: endNode(r).id, type: type(r), group_id: r.group_id}}] AS rls
    LIMIT 100
    """
    nodes_map: Dict[str, Dict] = {}
    links: List[Dict] = []

    print("DRIVER IN FUNC", driver._check_state())

    async with driver.session() as sess:
        print("SESSION", sess)
        res = await sess.run(cy, id=id_value)
        recs = await res.data()
        for rec in recs:
            for n in rec.get("nds", []):
                nid = n.get("id")
                if nid and nid not in nodes_map:
                    nodes_map[nid] = n
            for r in rec.get("rls", []):
                # dedupe edges by (start,end,type,group_id)
                links.append(r)

    # unique edges
    seen = set()
    uniq_links = []
    for l in links:
        key = (l.get("start"), l.get("end"), l.get("type"), l.get("group_id"))
        if key not in seen:
            seen.add(key)
            uniq_links.append(l)

    return {"nodes": list(nodes_map.values()), "links": uniq_links}
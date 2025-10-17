
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("status") == "ok"
    assert payload.get("service") == "course-graph-api"

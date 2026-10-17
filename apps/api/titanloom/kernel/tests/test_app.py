"""骨架自检：空应用能启动、健康检查可用。"""

from fastapi.testclient import TestClient

from titanloom.main import create_app


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

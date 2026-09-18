from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_overview_endpoint_after_pipeline():
    response = TestClient(app).get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["total_customers"] >= 5_000
    assert body["metrics"]["mrr"] > 0


def test_customer_not_found():
    response = TestClient(app).get("/api/customer/CUS-99999")
    assert response.status_code == 404

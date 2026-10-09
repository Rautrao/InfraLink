import pytest
from fastapi.testclient import TestClient
from app.main import app
from seed.seed import main as seed_demo_city

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        seed_demo_city()
        yield test_client

def login(client, email="admin@demo.city", password="demo1234"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]

@pytest.fixture
def admin_token(client):
    return login(client)

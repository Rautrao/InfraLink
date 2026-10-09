import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import engine
from sqlalchemy import text
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

@pytest.fixture(autouse=True)
def remove_test_work_after_test(client):
    yield
    related="select id from work where title like 'TEST: %'"
    with engine.begin() as connection:
        connection.execute(text(f"delete from ticket_event where ticket_id in (select id from feedback_ticket where work_id in ({related}))"))
        connection.execute(text(f"delete from feedback_ticket where work_id in ({related})"))
        connection.execute(text(f"delete from notification where work_id in ({related})"))
        connection.execute(text(f"delete from follow_subscription where work_id in ({related})"))
        connection.execute(text(f"delete from conflict_decision where alert_id in (select id from conflict_alert where work_a in ({related}) or work_b in ({related}))"))
        connection.execute(text(f"delete from conflict_alert where work_a in ({related}) or work_b in ({related})"))
        for table in ("permit","evidence","work_update","work_status_history","work_date_revision","work_milestone"):
            connection.execute(text(f"delete from {table} where work_id in ({related})"))
        connection.execute(text(f"delete from work where id in ({related})"))

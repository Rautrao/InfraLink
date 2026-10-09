from conftest import login
from app.modules.organisations.service import get_assignee

def test_reference_directories_and_assignee(client):
    assert len(client.get("/api/v1/agencies").json()) >= 5
    assert len(client.get("/api/v1/wards").json()) == 4
    assert len(client.get("/api/v1/zones").json()) == 4
    work_id=client.get("/api/v1/works?page_size=1").json()["items"][0]["id"]
    assignee=get_assignee(work_id,1)
    assert assignee and assignee["role"]=="junior_engineer"
    token = login(client, "je.ward1@demo.city")
    response = client.get("/api/v1/officers?ward_id=" + client.get("/api/v1/wards").json()[0]["id"], headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(client.get("/api/v1/escalation-ladder").json(), list)

def test_officer_directory_rejects_resident(client):
    client.post("/api/v1/auth/otp/request", json={"phone": "9000000001"})
    token = client.post("/api/v1/auth/otp/verify", json={"phone":"9000000001","otp":"123456"}).json()["access_token"]
    response = client.get("/api/v1/officers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

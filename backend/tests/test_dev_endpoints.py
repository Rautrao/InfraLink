from datetime import timedelta
from conftest import login
from app.core import clock
from app.core.config import settings

def test_advance_time_moves_and_restores_application_clock(client):
    start=clock.now()
    response=client.post("/api/v1/dev/advance-time",json={"days":2})
    assert response.status_code==200 and response.json()["advanced_days"]==2
    assert clock.now()-start >= timedelta(days=2)
    restored=client.post("/api/v1/dev/advance-time",json={"days":-2})
    assert restored.status_code==200
    assert abs((clock.now()-start).total_seconds()) < 10
    invalid=client.post("/api/v1/dev/advance-time",json={"days":3651})
    assert invalid.status_code==422

def test_dev_routes_require_admin_when_demo_mode_is_off(client,monkeypatch):
    monkeypatch.setattr(settings,"dev_mode",False)
    denied=client.post("/api/v1/dev/advance-time",json={"days":1})
    assert denied.status_code==401
    token=login(client,"admin@demo.city")
    allowed=client.post("/api/v1/dev/advance-time",headers={"Authorization":f"Bearer {token}"},json={"days":1})
    assert allowed.status_code==200
    client.post("/api/v1/dev/advance-time",headers={"Authorization":f"Bearer {token}"},json={"days":-1})
    denied_reset=client.post("/api/v1/dev/reset-seed")
    assert denied_reset.status_code==401
    reset=client.post("/api/v1/dev/reset-seed",headers={"Authorization":f"Bearer {token}"})
    assert reset.status_code==200 and reset.json()["status"]=="seed reset"

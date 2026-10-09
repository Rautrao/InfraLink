from conftest import login

def test_admin_can_read_update_and_restore_city_config(client):
    token=login(client,"admin@demo.city")
    headers={"Authorization":f"Bearer {token}"}
    original=client.get("/api/v1/admin/config",headers=headers)
    assert original.status_code==200
    config=original.json()
    updated=client.put("/api/v1/admin/config",headers=headers,json={"buffer_m":float(config["buffer_m"])+1,"features":{"demo_flag":True}})
    assert updated.status_code==200 and updated.json()["features"]["demo_flag"] is True
    restored=client.put("/api/v1/admin/config",headers=headers,json={"buffer_m":config["buffer_m"],"features":config["features"]})
    assert restored.status_code==200 and restored.json()["buffer_m"]==config["buffer_m"]

def test_city_config_rejects_non_admin(client):
    token=login(client,"je.ward1@demo.city")
    response=client.get("/api/v1/admin/config",headers={"Authorization":f"Bearer {token}"})
    assert response.status_code==403

from app.main import app

def test_health_route_is_registered():
    assert any(route.path == "/healthz" and "GET" in route.methods for route in app.routes)

def test_identity_and_module_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/geo_spatial/ping" in paths

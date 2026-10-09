"""Build the checked-in, dependency-free OpenAPI snapshot for the scaffold."""
import json
from pathlib import Path

paths = {
    "/healthz": {"get": {"tags": ["default"], "summary": "Healthz", "responses": {"200": {"description": "Successful Response"}}}},
    "/api/v1/auth/login": {"post": {"tags": ["identity and reference"], "summary": "Login", "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginBody"}}}}, "responses": {"200": {"description": "Successful Response"}, "401": {"description": "Invalid credentials"}}}},
    "/api/v1/auth/otp/request": {"post": {"tags": ["identity and reference"], "summary": "Request Otp", "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PhoneBody"}}}}, "responses": {"200": {"description": "OTP requested"}}}},
    "/api/v1/auth/otp/verify": {"post": {"tags": ["identity and reference"], "summary": "Verify Otp", "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/OtpBody"}}}}, "responses": {"200": {"description": "Successful Response"}}}},
    "/api/v1/auth/me": {"get": {"tags": ["identity and reference"], "summary": "Me", "security": [{"BearerAuth": []}], "responses": {"200": {"description": "Current user"}}}},
    "/api/v1/wards": {"get": {"tags": ["identity and reference"], "summary": "Wards", "responses": {"200": {"description": "Ward list"}}}},
    "/api/v1/agencies": {"get": {"tags": ["identity and reference"], "summary": "Agencies", "responses": {"200": {"description": "Agency list"}}}},
    "/api/v1/config/public": {"get": {"tags": ["identity and reference"], "summary": "Public Config", "responses": {"200": {"description": "Public configuration"}}}},
    "/api/v1/dev/advance-time": {"post": {"tags": ["default"], "summary": "Advance Time", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]}}}}, "responses": {"200": {"description": "Clock advanced"}}}},
    "/api/v1/dev/reset-seed": {"post": {"tags": ["default"], "summary": "Reset Seed", "responses": {"200": {"description": "Seed restored"}}}},
}
modules = ["organisations", "project_registry", "schedule_milestones", "audit", "admin_config", "imports", "geo_spatial", "permits", "conflict_engine", "evidence", "citizen_feedback", "notifications", "reporting", "public_api"]
for module in modules:
    paths[f"/api/v1/{module}/ping"] = {"get": {"tags": [module], "summary": f"{module.replace('_', ' ').title()} Ping", "responses": {"200": {"description": "Scaffold module status"}}}}
spec = {
    "openapi": "3.1.0",
    "info": {"title": "Public Works Transparency Platform", "version": "0.1.0"},
    "paths": paths,
    "components": {
        "securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
        "schemas": {
            "LoginBody": {"type": "object", "required": ["email", "password"], "properties": {"email": {"type": "string"}, "password": {"type": "string"}}},
            "PhoneBody": {"type": "object", "required": ["phone"], "properties": {"phone": {"type": "string"}}},
            "OtpBody": {"type": "object", "required": ["phone", "otp"], "properties": {"phone": {"type": "string"}, "otp": {"type": "string"}}},
        },
    },
}
Path(__file__).with_name("openapi.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

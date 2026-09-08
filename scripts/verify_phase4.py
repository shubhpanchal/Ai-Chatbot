"""Verification script for Phase 4 live endpoints against Docker container."""

import httpx

client = httpx.Client(base_url="http://localhost:8001", timeout=10.0)

# 1. Health Probe
r_health = client.get("/health")
print("1. GET /health:", r_health.status_code, r_health.json())
assert r_health.status_code == 200

# 2. Auth Rejection
r_unauth = client.get("/api/v1/conversations")
print("2. GET /api/v1/conversations (unauthenticated):", r_unauth.status_code, r_unauth.json())
assert r_unauth.status_code == 401
assert r_unauth.json()["error"]["code"] == "UNAUTHORIZED"

# 3. List seeded conversations with Dev API Key
dev_headers = {"Authorization": "Bearer ak_dev_seed_000000000000000000000000"}
r_list = client.get("/api/v1/conversations?page=1&page_size=5", headers=dev_headers)
data_list = r_list.json()
print("3. GET /api/v1/conversations (paginated):", r_list.status_code)
print(
    f"   Total: {data_list['total']}, Page: {data_list['page']}, Pages: {data_list['pages']}, Items count: {len(data_list['items'])}"
)
assert r_list.status_code == 200
assert data_list["total"] >= 50
assert len(data_list["items"]) == 5

# 4. Create new conversation
r_create = client.post(
    "/api/v1/conversations",
    json={
        "title": "Live Docker Verification Thread",
        "system_prompt": "You are a verification bot.",
    },
    headers=dev_headers,
)
print("4. POST /api/v1/conversations:", r_create.status_code, r_create.json())
assert r_create.status_code == 201
conv_id = r_create.json()["id"]

# 5. Get conversation details
r_get = client.get(f"/api/v1/conversations/{conv_id}", headers=dev_headers)
data_get = r_get.json()
print(f"5. GET /api/v1/conversations/{conv_id}:", r_get.status_code)
print(
    f"   Title: {data_get['title']}, Messages: {len(data_get['messages'])}, Usage: {data_get['usage_summary']}"
)
assert r_get.status_code == 200
assert data_get["title"] == "Live Docker Verification Thread"

# 6. Soft delete conversation
r_del = client.delete(f"/api/v1/conversations/{conv_id}", headers=dev_headers)
print(f"6. DELETE /api/v1/conversations/{conv_id}:", r_del.status_code)
assert r_del.status_code == 204

# 7. Verify soft-deleted returns 404
r_get_deleted = client.get(f"/api/v1/conversations/{conv_id}", headers=dev_headers)
print(
    f"7. GET deleted /api/v1/conversations/{conv_id}:",
    r_get_deleted.status_code,
    r_get_deleted.json(),
)
assert r_get_deleted.status_code == 404
assert r_get_deleted.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

print("\nAll live Phase 4 endpoints verified successfully against Docker container!")

def test_admin_list_users(client, admin_headers):
    resp = client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1


def test_non_admin_denied(client, user_headers):
    resp = client.get("/api/admin/users", headers=user_headers)
    assert resp.status_code == 403


def test_admin_change_role(client, admin_headers, user_headers):
    users_resp = client.get("/api/admin/users", headers=admin_headers)
    users = users_resp.json()
    regular_user = next((u for u in users if u["role"] == "user"), None)
    if regular_user:
        resp = client.put(
            f"/api/admin/users/{regular_user['id']}/role",
            json={"role": "admin"}, headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


def test_admin_cannot_change_own_role(client, admin_headers):
    me_resp = client.get("/api/auth/me", headers=admin_headers)
    my_id = me_resp.json()["id"]
    resp = client.put(f"/api/admin/users/{my_id}/role", json={"role": "user"}, headers=admin_headers)
    assert resp.status_code == 400


def test_admin_cannot_delete_self(client, admin_headers):
    me_resp = client.get("/api/auth/me", headers=admin_headers)
    my_id = me_resp.json()["id"]
    resp = client.delete(f"/api/admin/users/{my_id}", headers=admin_headers)
    assert resp.status_code == 400


def test_admin_system_info(client, admin_headers):
    resp = client.get("/api/admin/system", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_media" in data


def test_admin_libraries_list(client, admin_headers):
    resp = client.get("/api/admin/libraries", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_logs(client, admin_headers):
    resp = client.get("/api/admin/logs", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()

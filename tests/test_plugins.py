def test_list_plugins(client, admin_headers):
    resp = client.get("/api/plugins", headers=admin_headers)
    assert resp.status_code == 200
    plugins = resp.json()
    assert isinstance(plugins, list)


def test_plugins_denied_for_user(client, user_headers):
    resp = client.get("/api/plugins", headers=user_headers)
    assert resp.status_code == 403


def test_cast_devices(client, admin_headers):
    resp = client.get("/api/cast/devices", headers=admin_headers)
    assert resp.status_code == 200
    assert "devices" in resp.json()


def test_cast_status_no_device(client, admin_headers):
    resp = client.get("/api/cast/status", headers=admin_headers)
    assert resp.status_code == 200

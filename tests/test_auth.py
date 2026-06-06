def test_register_first_user_is_admin(client):
    resp = client.post("/api/auth/register", json={"username": "firstuser", "password": "pass1234"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["username"] == "firstuser"


def test_register_second_user_is_regular(client):
    client.post("/api/auth/register", json={"username": "admin1", "password": "admin123"})
    resp = client.post("/api/auth/register", json={"username": "user2", "password": "pass1234"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"username": "testuser", "password": "pass1234"})
    resp = client.post("/api/auth/register", json={"username": "testuser", "password": "pass5678"})
    assert resp.status_code == 409


def test_register_short_username(client):
    resp = client.post("/api/auth/register", json={"username": "ab", "password": "pass1234"})
    assert resp.status_code == 400


def test_login_success(client):
    client.post("/api/auth/register", json={"username": "loginuser", "password": "pass1234"})
    resp = client.post("/api/auth/login", data={"username": "loginuser", "password": "pass1234"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"username": "loginuser", "password": "pass1234"})
    resp = client.post("/api/auth/login", data={"username": "loginuser", "password": "wrong"})
    assert resp.status_code == 401


def test_me_endpoint(client, admin_token):
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin1"
    assert data["role"] == "admin"


def test_me_invalid_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401

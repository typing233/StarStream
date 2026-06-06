import os
import tempfile


def test_create_library(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        resp = client.post("/api/libraries", json={"name": "Test Lib", "path": tmpdir}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Lib"


def test_create_library_invalid_path(client, admin_headers):
    resp = client.post("/api/libraries", json={"name": "Bad", "path": "/nonexistent/path"}, headers=admin_headers)
    assert resp.status_code == 400


def test_list_libraries(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        client.post("/api/libraries", json={"name": "Lib1", "path": tmpdir}, headers=admin_headers)
        resp = client.get("/api/libraries", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


def test_delete_library(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        create_resp = client.post("/api/libraries", json={"name": "ToDelete", "path": tmpdir}, headers=admin_headers)
        lib_id = create_resp.json()["id"]
        resp = client.delete(f"/api/libraries/{lib_id}", headers=admin_headers)
        assert resp.status_code == 200


def test_list_media_pagination(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        create_resp = client.post("/api/libraries", json={"name": "PagLib", "path": tmpdir}, headers=admin_headers)
        lib_id = create_resp.json()["id"]
        resp = client.get(f"/api/libraries/{lib_id}/media?page=1&per_page=10", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data


def test_list_media_sort(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        create_resp = client.post("/api/libraries", json={"name": "SortLib", "path": tmpdir}, headers=admin_headers)
        lib_id = create_resp.json()["id"]
        resp = client.get(f"/api/libraries/{lib_id}/media?sort=title&order=desc", headers=admin_headers)
        assert resp.status_code == 200


def test_user_cannot_see_other_libraries(client, admin_headers, user_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        client.post("/api/libraries", json={"name": "AdminLib", "path": tmpdir}, headers=admin_headers)
        resp = client.get("/api/libraries", headers=user_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0


def test_search_endpoint(client, admin_headers):
    resp = client.get("/api/search?q=test", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data

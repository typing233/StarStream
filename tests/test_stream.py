import tempfile
import os


def test_stream_unauthorized(client):
    resp = client.get("/api/stream/1")
    assert resp.status_code in (401, 403)


def test_stream_nonexistent_media(client, admin_headers):
    resp = client.get("/api/stream/99999", headers=admin_headers)
    assert resp.status_code == 404


def test_cover_nonexistent(client, admin_headers):
    resp = client.get("/api/stream/99999/cover", headers=admin_headers)
    assert resp.status_code == 404


def test_info_nonexistent(client, admin_headers):
    resp = client.get("/api/stream/99999/info", headers=admin_headers)
    assert resp.status_code == 404


def test_stream_access_denied(client, admin_headers, user_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        from tests.conftest import TestingSessionLocal
        from app.models import Library, MediaItem

        lib_resp = client.post("/api/libraries", json={"name": "PrivLib", "path": tmpdir}, headers=admin_headers)
        lib_id = lib_resp.json()["id"]

        test_file = os.path.join(tmpdir, "secret.mp4")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        db = TestingSessionLocal()
        item = MediaItem(
            library_id=lib_id, title="Secret Video", media_type="video",
            file_path=test_file, file_size=100,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        media_id = item.id
        db.close()

        resp = client.get(f"/api/stream/{media_id}", headers=user_headers)
        assert resp.status_code == 403

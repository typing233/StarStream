import tempfile
import os


def test_record_play_event(client, admin_headers):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a library and manually insert a media item for testing
        from tests.conftest import TestingSessionLocal
        from app.models import Library, MediaItem

        lib_resp = client.post("/api/libraries", json={"name": "StatsLib", "path": tmpdir}, headers=admin_headers)
        lib_id = lib_resp.json()["id"]

        db = TestingSessionLocal()
        item = MediaItem(
            library_id=lib_id, title="Test Video", media_type="video",
            file_path=os.path.join(tmpdir, "test.mp4"), file_size=1000,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        media_id = item.id
        db.close()

        resp = client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 120.5, "completed": False,
        }, headers=admin_headers)
        assert resp.status_code == 200


def test_get_history(client, admin_headers):
    resp = client.get("/api/stats/history", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_get_popular(client, admin_headers):
    resp = client.get("/api/stats/popular", headers=admin_headers)
    assert resp.status_code == 200


def test_get_summary(client, admin_headers):
    resp = client.get("/api/stats/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_plays" in data
    assert "total_hours_watched" in data
    assert "unique_items_played" in data


def test_admin_stats_overview(client, admin_headers):
    resp = client.get("/api/stats/admin/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_plays" in data
    assert "total_users" in data


def test_admin_stats_denied_for_user(client, user_headers):
    resp = client.get("/api/stats/admin/overview", headers=user_headers)
    assert resp.status_code == 403

"""
Targeted tests for round 2 fixes:
1. Login and upload use base URL (sub-path deployment)
2. Play stats don't double-count (delta-based reporting)
3. Scanner emits media_added AFTER commit (plugin can read records)
"""
import os
import sys
import tempfile
import io

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.models import Library, MediaItem, PlayEvent


# ─── Test 1: Sub-path login and upload ───────────────────────────────────────

class TestBaseUrlSubPath:
    """Test that login and upload work when app is behind a sub-path (root_path)."""

    def test_login_under_subpath(self, client, admin_token):
        """Login endpoint must be accessible at root_path + /api/auth/login."""
        resp = client.post("/api/auth/login", data={"username": "admin1", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_upload_under_subpath(self, client, admin_token):
        """Upload endpoint must be accessible and functional."""
        file_content = b"fake audio data"
        files = [("files", ("test.mp3", io.BytesIO(file_content), "audio/mpeg"))]
        resp = client.post(
            "/api/libraries/upload",
            data={"name": "SubpathLib"},
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "SubpathLib"
        assert data["id"] > 0

    def test_login_returns_valid_token_for_subsequent_api(self, client):
        """Full flow: register -> login -> use token to call /api/auth/me."""
        client.post("/api/auth/register", json={"username": "flow_user", "password": "pass1234"})
        login_resp = client.post("/api/auth/login", data={"username": "flow_user", "password": "pass1234"})
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "flow_user"


# ─── Test 2: Play stats delta (no double-counting) ──────────────────────────

class TestPlayStatsDelta:
    """Verify that multiple play reports accumulate correctly without double-counting."""

    def _create_media(self, client, admin_token):
        """Helper: create a library with one media item."""
        from app.main import app

        db = next(app.dependency_overrides[get_db]())
        lib = Library(name="TestLib", path="/tmp/test_media_stats", owner_id=1)
        db.add(lib)
        db.commit()
        db.refresh(lib)

        item = MediaItem(
            library_id=lib.id, title="Test Video", media_type="video",
            file_path="/tmp/test_media_stats/video.mp4", file_size=1000,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        db.close()
        return item.id

    def test_pause_then_leave_no_double_count(self, client, admin_token):
        """Simulates: play 30s, pause (report delta=30), play 20 more, leave (report delta=20).
        Total should be 50, not 80."""
        from app.main import app
        media_id = self._create_media(client, admin_token)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # First pause: delta = 30 seconds
        resp = client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 30, "completed": False
        }, headers=headers)
        assert resp.status_code == 200

        # Leave page: delta = 20 seconds
        resp = client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 20, "completed": False
        }, headers=headers)
        assert resp.status_code == 200

        # Check total directly from DB
        db = next(app.dependency_overrides[get_db]())
        total = db.query(func.sum(PlayEvent.duration_watched)).scalar()
        db.close()
        assert total == 50

    def test_multiple_pauses_report_deltas(self, client, admin_token):
        """Multiple pauses should each report only the new delta."""
        from app.main import app
        media_id = self._create_media(client, admin_token)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Pause 1: delta=10
        client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 10, "completed": False
        }, headers=headers)

        # Pause 2: delta=15
        client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 15, "completed": False
        }, headers=headers)

        # Pause 3: delta=5
        client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 5, "completed": False
        }, headers=headers)

        # End: delta=10, completed
        client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 10, "completed": True
        }, headers=headers)

        # 10 + 15 + 5 + 10 = 40 total
        db = next(app.dependency_overrides[get_db]())
        total = db.query(func.sum(PlayEvent.duration_watched)).scalar()
        count = db.query(PlayEvent).count()
        db.close()
        assert total == 40
        assert count == 4

    def test_completed_event_recorded(self, client, admin_token):
        """Verify completed flag is stored correctly."""
        media_id = self._create_media(client, admin_token)
        headers = {"Authorization": f"Bearer {admin_token}"}

        client.post("/api/stats/play", json={
            "media_id": media_id, "duration_watched": 60, "completed": True
        }, headers=headers)

        history = client.get("/api/stats/history", headers=headers).json()
        assert len(history["items"]) == 1
        assert history["items"][0]["completed"] is True
        assert history["items"][0]["duration_watched"] == 60


# ─── Test 3: Scanner emits media_added AFTER commit ─────────────────────────

class TestScannerEmitAfterCommit:
    """Verify that plugin receives media_added AFTER db commit,
    so it can query the record from its own session."""

    def _get_test_session_factory(self):
        from app.main import app
        db_gen = app.dependency_overrides[get_db]
        return db_gen

    def test_media_added_fires_after_commit(self, client, admin_token):
        """When scan_library runs, media_added hook should be called
        with media_id that is queryable from a separate DB session."""
        from app.main import app
        get_test_db = app.dependency_overrides[get_db]

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "TestMovie (2023).mp4")
            with open(test_file, "wb") as f:
                f.write(b"\x00" * 1024)

            db = next(get_test_db())
            lib = Library(name="ScanTest", path=tmpdir, owner_id=1)
            db.add(lib)
            db.commit()
            db.refresh(lib)
            lib_id = lib.id
            db.close()

            emitted_events = []
            readable_items = []

            def capture_emit(event_name, data):
                if event_name == "media_added":
                    emitted_events.append(data)
                    check_db = next(get_test_db())
                    item = check_db.query(MediaItem).filter(MediaItem.id == data["media_id"]).first()
                    if item:
                        readable_items.append({"id": item.id, "title": item.title})
                    check_db.close()

            # Patch both the plugin_manager.emit AND SessionLocal to use test DB
            from tests.conftest import TestingSessionLocal
            with patch("app.services.scanner.SessionLocal", TestingSessionLocal), \
                 patch("app.services.plugin_manager.plugin_manager.emit", side_effect=capture_emit):
                from app.services.scanner import scan_library
                scan_library(lib_id)

            assert len(emitted_events) == 1
            assert emitted_events[0]["media_type"] == "video"
            assert "TestMovie" in emitted_events[0]["title"]
            assert emitted_events[0]["media_id"] is not None

            # Critical: plugin could read the item at emit time
            assert len(readable_items) == 1
            assert readable_items[0]["id"] == emitted_events[0]["media_id"]

    def test_multiple_files_all_committed_before_emit(self, client, admin_token):
        """All items should be committed before any media_added fires."""
        from app.main import app
        get_test_db = app.dependency_overrides[get_db]

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                with open(os.path.join(tmpdir, f"video{i}.mp4"), "wb") as f:
                    f.write(b"\x00" * 512)

            db = next(get_test_db())
            lib = Library(name="MultiScan", path=tmpdir, owner_id=1)
            db.add(lib)
            db.commit()
            db.refresh(lib)
            lib_id = lib.id
            db.close()

            emit_order = []
            items_visible_at_emit = []

            def capture_emit(event_name, data):
                if event_name == "media_added":
                    emit_order.append(data["media_id"])
                    check_db = next(get_test_db())
                    count = check_db.query(MediaItem).filter(MediaItem.library_id == lib_id).count()
                    items_visible_at_emit.append(count)
                    check_db.close()

            from tests.conftest import TestingSessionLocal
            with patch("app.services.scanner.SessionLocal", TestingSessionLocal), \
                 patch("app.services.plugin_manager.plugin_manager.emit", side_effect=capture_emit):
                from app.services.scanner import scan_library
                scan_library(lib_id)

            assert len(emit_order) == 3
            # All 3 items visible at time of each emit (committed before emit loop)
            for count in items_visible_at_emit:
                assert count == 3

    def test_plugin_metadata_writeback(self, client, admin_token):
        """Simulate the metadata plugin: on media_added, query and update title."""
        from app.main import app
        get_test_db = app.dependency_overrides[get_db]

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "some_movie.mp4")
            with open(test_file, "wb") as f:
                f.write(b"\x00" * 1024)

            db = next(get_test_db())
            lib = Library(name="WritebackTest", path=tmpdir, owner_id=1)
            db.add(lib)
            db.commit()
            db.refresh(lib)
            lib_id = lib.id
            db.close()

            def plugin_like_emit(event_name, data):
                if event_name == "media_added":
                    from tests.conftest import TestingSessionLocal
                    plugin_db = TestingSessionLocal()
                    item = plugin_db.query(MediaItem).filter(MediaItem.id == data["media_id"]).first()
                    assert item is not None, "Plugin must be able to read item after emit"
                    item.title = "Scraped Title From OMDb"
                    plugin_db.commit()
                    plugin_db.close()

            from tests.conftest import TestingSessionLocal
            with patch("app.services.scanner.SessionLocal", TestingSessionLocal), \
                 patch("app.services.plugin_manager.plugin_manager.emit", side_effect=plugin_like_emit):
                from app.services.scanner import scan_library
                scan_library(lib_id)

            verify_db = next(get_test_db())
            item = verify_db.query(MediaItem).filter(MediaItem.library_id == lib_id).first()
            assert item is not None
            assert item.title == "Scraped Title From OMDb"
            verify_db.close()

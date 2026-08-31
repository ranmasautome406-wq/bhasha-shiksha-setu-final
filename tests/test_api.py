"""
End-to-end API tests for Bhasha Shiksha Setu.
Run:  pytest tests/ -v        (from the project root)
Uses an isolated temporary SQLite database — your real data is untouched.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.config import Config
from backend.database import init_db


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    """Reset the in-memory login lockout / rate limit counters between tests."""
    import backend.utils as u
    u._attempts.clear()
    yield
    u._attempts.clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("SEED_DEMO", "false")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.setu")
    monkeypatch.setenv("ADMIN_PASSWORD", "Admin@123")

    from backend.app import create_app
    app = create_app(Config)
    app.config["TESTING"] = True
    return app.test_client()


def auth_headers(client, identifier="admin@test.setu", password="Admin@123"):
    res = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, res.get_json()
    return {"Authorization": "Bearer " + res.get_json()["data"]["token"]}


# ------------------------ health & basics ------------------------
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    d = r.get_json()["data"]
    assert d["project"] == "Bhasha Shiksha Setu"
    assert d["problem_statement"] == "SIH26042"


def test_public_content_and_config(client):
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/content").status_code == 200
    assert client.get("/api/lessons").status_code == 200


# ------------------------ auth ------------------------
def test_login_ok_and_wrong_password(client):
    r = client.post("/api/auth/login", json={"identifier": "admin@test.setu", "password": "wrong-pass"})
    assert r.status_code == 401
    assert r.get_json()["success"] is False

    r = client.post("/api/auth/login", json={"identifier": "admin@test.setu", "password": "Admin@123"})
    assert r.status_code == 200
    assert "token" in r.get_json()["data"]


def test_protected_route_requires_token(client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/student/dashboard").status_code == 401


def test_role_access_control(client):
    # register a student, then try admin routes
    r = client.post("/api/auth/register", json={
        "name": "Test Student", "email": "s@test.setu", "password": "secret1",
        "language_preference": "Marathi"})
    assert r.status_code == 201
    token = r.get_json()["data"]["token"]
    h = {"Authorization": "Bearer " + token}
    assert client.get("/api/admin/dashboard", headers=h).status_code == 403
    assert client.get("/api/student/dashboard", headers=h).status_code == 200


def test_brute_force_lockout(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"identifier": "admin@test.setu", "password": "x"})
    r = client.post("/api/auth/login", json={"identifier": "admin@test.setu", "password": "Admin@123"})
    assert r.status_code == 429  # locked out even with the right password


def test_change_password(client):
    h = auth_headers(client)
    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": "Admin@123", "new_password": "NewPass#1"})
    assert r.status_code == 200
    # old password no longer works
    r = client.post("/api/auth/login", json={"identifier": "admin@test.setu", "password": "Admin@123"})
    assert r.status_code == 401


# ------------------------ admin: users ------------------------
def test_admin_user_crud(client):
    h = auth_headers(client)
    r = client.post("/api/users", headers=h, json={
        "name": "New Teacher", "email": "t@test.setu", "role": "teacher", "password": "pass1234"})
    assert r.status_code == 201
    uid = r.get_json()["data"]["id"]

    r = client.get("/api/users?q=t@test.setu", headers=h)
    assert r.status_code == 200 and len(r.get_json()["data"]) == 1

    r = client.put(f"/api/users/{uid}", headers=h, json={"name": "Renamed Teacher"})
    assert r.status_code == 200 and r.get_json()["data"]["name"] == "Renamed Teacher"

    r = client.delete(f"/api/users/{uid}", headers=h)
    assert r.status_code == 200


# ------------------------ admin: dashboard ------------------------
def test_admin_dashboard_stats(client):
    h = auth_headers(client)
    r = client.get("/api/admin/dashboard", headers=h)
    assert r.status_code == 200
    stats = r.get_json()["data"]["stats"]
    for key in ["total_students", "total_teachers", "total_lessons",
                "total_ai_questions", "active_users"]:
        assert key in stats


# ------------------------ lessons ------------------------
def test_lesson_lifecycle(client):
    h = auth_headers(client)
    body = {
        "title": "Test Lesson", "subject": "Science", "grade": "8", "language": "Marathi",
        "status": "draft",
        "content_items": [{"type": "text", "title": "Intro", "content": "Hello world", "sort_order": 0}],
    }
    r = client.post("/api/teacher/lessons", headers=h, json=body)
    assert r.status_code == 201
    lid = r.get_json()["data"]["id"]

    # drafts hidden from public
    assert client.get("/api/lessons").status_code == 200
    assert client.get(f"/api/lessons/{lid}").status_code == 404

    # publish
    r = client.post(f"/api/teacher/lessons/{lid}/publish", headers=h)
    assert r.status_code == 200
    assert client.get(f"/api/lessons/{lid}").status_code == 200

    # update
    r = client.put(f"/api/teacher/lessons/{lid}", headers=h,
                   json={"description": "updated", "language": "Hindi"})
    assert r.status_code == 200 and r.get_json()["data"]["language"] == "Hindi"

    # delete
    r = client.delete(f"/api/teacher/lessons/{lid}", headers=h)
    assert r.status_code == 200


# ------------------------ student progress ------------------------
def test_student_progress(client):
    client.post("/api/auth/register", json={
        "name": "Prog Student", "email": "p@test.setu", "password": "secret1"})
    r = client.post("/api/auth/login", json={"identifier": "p@test.setu", "password": "secret1"})
    h = {"Authorization": "Bearer " + r.get_json()["data"]["token"]}

    # publish a lesson as admin
    ah = auth_headers(client)
    r = client.post("/api/teacher/lessons", headers=ah, json={
        "title": "Water Cycle", "subject": "Science", "status": "published"})
    lid = r.get_json()["data"]["id"]

    r = client.post("/api/student/progress", headers=h,
                    json={"lesson_id": lid, "status": "completed", "progress": 100})
    assert r.status_code == 200

    r = client.get("/api/student/dashboard", headers=h)
    d = r.get_json()["data"]
    assert d["stats"]["completed"] == 1
    assert d["language_preference"] == "English"
    assert any(x["id"] == lid for x in d["completed_lessons"])


# ------------------------ AI + translation ------------------------
def test_chat_and_translation(client):
    guest = {"X-Guest-Id": "testguest1"}
    r = client.post("/api/chat", json={"message": "Explain photosynthesis", "language": "English"},
                    headers=guest)
    assert r.status_code == 200
    assert "photosynthesis" in r.get_json()["data"]["reply"].lower() or "process" in r.get_json()["data"]["reply"].lower()

    r = client.get("/api/chat/history", headers=guest)
    assert r.status_code == 200 and len(r.get_json()["data"]) >= 1

    r = client.delete("/api/chat/history", headers=guest)
    assert r.status_code == 200
    assert client.get("/api/chat/history", headers=guest).get_json()["data"] == []

    r = client.post("/api/translate", json={
        "text": "hello teacher", "source_language": "English", "target_language": "Marathi"})
    assert r.status_code == 200
    assert r.get_json()["data"]["translated_text"]


# ------------------------ media upload ------------------------
def test_media_upload_and_serve(client):
    h = auth_headers(client)
    data = {"file": (io_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100), "test.png", "image/png")}
    r = client.post("/api/admin/media", headers=h, data=data, content_type="multipart/form-data")
    assert r.status_code == 201
    media = r.get_json()["data"]

    # accessible publicly
    r = client.get(media["url"])
    assert r.status_code == 200

    # reject dangerous file types
    data = {"file": (io_bytes(b"MZ..."), "evil.exe", "application/octet-stream")}
    r = client.post("/api/admin/media", headers=h, data=data, content_type="multipart/form-data")
    assert r.status_code in (400, 500)


def io_bytes(b):
    import io
    return io.BytesIO(b)


# ------------------------ content CMS ------------------------
def test_admin_content_roundtrip(client):
    h = auth_headers(client)
    r = client.put("/api/admin/content/text", headers=h, json={"hero_title": "Learn Free!"})
    assert r.status_code == 200

    r = client.put("/api/admin/settings", headers=h, json={"website_name": "BSS Test"})
    assert r.status_code == 200

    # announcement appears on the public endpoint
    r = client.post("/api/admin/announcements", headers=h, json={
        "title": "Test Announcement", "message": "New lessons added!", "priority": 9, "active": True})
    assert r.status_code == 201
    r = client.get("/api/content/announcements")
    assert any(a["title"] == "Test Announcement" for a in r.get_json()["data"])

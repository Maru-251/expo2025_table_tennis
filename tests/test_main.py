import os
import pytest
from fastapi.testclient import TestClient

import main
from sqlmodel import SQLModel, create_engine, Session

@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    main.DATABASE_URL = database_url
    main.engine = engine

    def override_get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[main.get_session] = override_get_session
    SQLModel.metadata.create_all(engine)
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def get_token(client, username, password):
    response = client.post(
        "/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_user_registration_and_login(client):
    resp = client.post(
        "/register",
        data={"username": "alice", "password": "password"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    token = get_token(client, "alice", "password")
    assert token


def test_crud_notes(client):
    client.post("/register", data={"username": "bob", "password": "pass"})
    token = get_token(client, "bob", "pass")

    note_data = {"category": "todo", "title": "t1", "description": "d1"}
    resp = client.post("/api/notes", json=note_data, headers=auth_header(token))
    assert resp.status_code == 200
    note = resp.json()
    note_id = note["id"]

    resp = client.get("/api/notes", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    updated = {"category": "done", "title": "t2", "description": "d2"}
    resp = client.put(f"/api/notes/{note_id}", json=updated, headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "t2"

    resp = client.delete(f"/api/notes/{note_id}", headers=auth_header(token))
    assert resp.status_code == 200

    resp = client.get("/api/notes", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_auth_failure(client):
    # no token
    resp = client.get("/api/notes")
    assert resp.status_code == 401

    # create user and note
    client.post("/register", data={"username": "alice", "password": "a"})
    token1 = get_token(client, "alice", "a")
    note_data = {"category": "c", "title": "t", "description": "d"}
    resp = client.post("/api/notes", json=note_data, headers=auth_header(token1))
    note_id = resp.json()["id"]

    client.post("/register", data={"username": "eve", "password": "e"})
    token2 = get_token(client, "eve", "e")

    resp = client.delete(f"/api/notes/{note_id}", headers=auth_header(token2))
    assert resp.status_code == 403

"""
Pytest configuration and fixtures for backend tests.
"""
import os
import sys
import pytest

os.environ["DB_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import User
from app.security import hash_password
from app import database


test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Set up test database before each test and tear down after.
    """
    original_engine = database.engine
    original_sessionlocal = database.SessionLocal
    
    database.engine = test_engine
    database.SessionLocal = TestSessionLocal
    
    Base.metadata.create_all(bind=test_engine)
    
    db = TestSessionLocal()
    try:
        admin_user = User(
            username="testadmin",
            password_hash=hash_password("admin123"),
            role="admin"
        )
        viewer_user = User(
            username="testviewer",
            password_hash=hash_password("viewer123"),
            role="viewer"
        )
        db.add(admin_user)
        db.add(viewer_user)
        db.commit()
    finally:
        db.close()
    
    yield
    
    Base.metadata.drop_all(bind=test_engine)
    
    database.engine = original_engine
    database.SessionLocal = original_sessionlocal


@pytest.fixture(scope="function")
def client():
    """
    Create a test client.
    """
    from app.main import app
    
    app.router.on_startup = []
    
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def admin_token(client):
    """
    Get a valid admin token for testing protected routes.
    """
    response = client.post(
        "/auth/token",
        json={"username": "testadmin", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def viewer_token(client):
    """
    Get a valid viewer token for testing protected routes.
    """
    response = client.post(
        "/auth/token",
        json={"username": "testviewer", "password": "viewer123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def admin_headers(admin_token):
    """
    Get authorization headers with admin token.
    """
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def viewer_headers(viewer_token):
    """
    Get authorization headers with viewer token.
    """
    return {"Authorization": f"Bearer {viewer_token}"}

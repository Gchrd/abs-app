"""
Integration tests for authentication and protected routes.

Tests cover:
1. POST /auth/token - Token issuance with valid/invalid credentials
2. GET /auth/me - Current user info retrieval
3. Protected routes - Authorization checks for admin-only endpoints
"""
import pytest
from fastapi import status


class TestAuthToken:
    """Tests for POST /login endpoint."""
    
    def test_login_with_valid_admin_credentials(self, client):
        """Test successful login with valid admin credentials."""
        response = client.post(
            "/login",
            json={"username": "testadmin", "password": "admin123"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
    
    def test_login_with_valid_viewer_credentials(self, client):
        """Test successful login with valid viewer credentials."""
        response = client.post(
            "/login",
            json={"username": "testviewer", "password": "viewer123"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "testviewer"
        assert data["role"] == "viewer"
    
    def test_login_with_invalid_username(self, client):
        """Test login fails with non-existent username."""
        response = client.post(
            "/login",
            json={"username": "nonexistent", "password": "anypassword"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Invalid credentials"
    
    def test_login_with_invalid_password(self, client):
        """Test login fails with incorrect password."""
        response = client.post(
            "/login",
            json={"username": "testadmin", "password": "wrongpassword"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Invalid credentials"
    
    def test_login_with_empty_credentials(self, client):
        """Test login fails with empty credentials."""
        response = client.post(
            "/login",
            json={"username": "", "password": ""}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_without_username(self, client):
        """Test login fails when username is missing."""
        response = client.post(
            "/login",
            json={"password": "admin123"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_login_without_password(self, client):
        """Test login fails when password is missing."""
        response = client.post(
            "/login",
            json={"username": "testadmin"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAuthMe:
    """Tests for GET /me endpoint."""
    
    def test_get_current_user_with_admin_token(self, client, admin_headers):
        """Test retrieving current user info with valid admin token."""
        response = client.get("/me", headers=admin_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"
    
    def test_get_current_user_with_viewer_token(self, client, viewer_headers):
        """Test retrieving current user info with valid viewer token."""
        response = client.get("/me", headers=viewer_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testviewer"
        assert data["role"] == "viewer"
    
    def test_get_current_user_without_token(self, client):
        """Test GET /me fails without authentication token."""
        response = client.get("/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_current_user_with_invalid_token(self, client):
        """Test GET /me fails with invalid token."""
        response = client.get(
            "/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in response.json()["detail"]
    
    def test_get_current_user_with_malformed_auth_header(self, client):
        """Test GET /me fails with malformed authorization header."""
        response = client.get(
            "/me",
            headers={"Authorization": "InvalidFormat"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestProtectedRoutes:
    """Tests for authorization on protected routes."""
    
    # Device routes tests
    
    def test_get_devices_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /devices."""
        response = client.get("/devices", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_devices_with_viewer_token(self, client, viewer_headers):
        """Test viewer can access GET /devices (read-only route)."""
        response = client.get("/devices", headers=viewer_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_devices_without_token(self, client):
        """Test GET /devices fails without authentication."""
        response = client.get("/devices")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_device_with_admin_token(self, client, admin_headers):
        """Test admin can create device."""
        device_data = {
            "hostname": "test-device",
            "ip": "192.168.1.100",
            "vendor": "cisco_ios",
            "protocol": "ssh",
            "port": 22,
            "username": "testuser",
            "password": "testpass",
            "tags": "test"
        }
        response = client.post("/devices", json=device_data, headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["hostname"] == "test-device"
        assert data["ip"] == "192.168.1.100"
    
    def test_create_device_with_viewer_token(self, client, viewer_headers):
        """Test viewer cannot create device (403 Forbidden)."""
        device_data = {
            "hostname": "test-device",
            "ip": "192.168.1.100",
            "vendor": "cisco_ios",
            "protocol": "ssh",
            "port": 22,
            "username": "testuser",
            "password": "testpass",
            "tags": "test"
        }
        response = client.post("/devices", json=device_data, headers=viewer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_create_device_without_token(self, client):
        """Test creating device fails without authentication."""
        device_data = {
            "hostname": "test-device",
            "ip": "192.168.1.100",
            "vendor": "cisco_ios",
            "protocol": "ssh",
            "port": 22,
            "username": "testuser",
            "password": "testpass",
            "tags": "test"
        }
        response = client.post("/devices", json=device_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Job routes tests
    
    def test_get_jobs_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /jobs."""
        response = client.get("/jobs", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_jobs_with_viewer_token(self, client, viewer_headers):
        """Test viewer can access GET /jobs (read-only route)."""
        response = client.get("/jobs", headers=viewer_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_jobs_without_token(self, client):
        """Test GET /jobs fails without authentication."""
        response = client.get("/jobs")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_run_manual_job_with_admin_token(self, client, admin_headers):
        """Test admin can run manual backup job."""
        response = client.post("/jobs/run/manual", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "queued" in data
        assert data["queued"] is True
    
    def test_run_manual_job_with_viewer_token(self, client, viewer_headers):
        """Test viewer cannot run manual backup job (403 Forbidden)."""
        response = client.post("/jobs/run/manual", headers=viewer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_run_manual_job_without_token(self, client):
        """Test running manual job fails without authentication."""
        response = client.post("/jobs/run/manual")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Schedule routes tests
    
    def test_get_schedules_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /schedules."""
        response = client.get("/schedules", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_schedules_with_viewer_token(self, client, viewer_headers):
        """Test viewer can access GET /schedules (read-only route)."""
        response = client.get("/schedules", headers=viewer_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_schedules_without_token(self, client):
        """Test GET /schedules fails without authentication."""
        response = client.get("/schedules")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_schedule_with_admin_token(self, client, admin_headers):
        """Test admin can create schedule."""
        schedule_data = {
            "schedule_time": "02:00",
            "interval_days": 1,
            "enabled": True
        }
        response = client.post("/schedules", json=schedule_data, headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["interval_days"] == 1
    
    def test_create_schedule_with_viewer_token(self, client, viewer_headers):
        """Test viewer cannot create schedule (403 Forbidden)."""
        schedule_data = {
            "schedule_time": "02:00",
            "interval_days": 1,
            "enabled": True
        }
        response = client.post("/schedules", json=schedule_data, headers=viewer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_create_schedule_without_token(self, client):
        """Test creating schedule fails without authentication."""
        schedule_data = {
            "schedule_time": "02:00",
            "interval_days": 1,
            "enabled": True
        }
        response = client.post("/schedules", json=schedule_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # User routes tests
    
    def test_get_users_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /users."""
        response = client.get("/users", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_users_with_viewer_token(self, client, viewer_headers):
        """Test viewer can access GET /users (read-only route)."""
        response = client.get("/users", headers=viewer_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_users_without_token(self, client):
        """Test GET /users fails without authentication."""
        response = client.get("/users")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_user_with_admin_token(self, client, admin_headers):
        """Test admin can create user."""
        user_data = {
            "username": "newuser",
            "password": "newpass123",
            "role": "viewer"
        }
        response = client.post("/users", json=user_data, headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "newuser"
        assert data["role"] == "viewer"
    
    def test_create_user_with_viewer_token(self, client, viewer_headers):
        """Test viewer cannot create user (403 Forbidden)."""
        user_data = {
            "username": "newuser",
            "password": "newpass123",
            "role": "viewer"
        }
        response = client.post("/users", json=user_data, headers=viewer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_create_user_without_token(self, client):
        """Test creating user fails without authentication."""
        user_data = {
            "username": "newuser",
            "password": "newpass123",
            "role": "viewer"
        }
        response = client.post("/users", json=user_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Audit log routes tests
    
    def test_get_audit_logs_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /audit-logs."""
        response = client.get("/audit-logs", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_audit_logs_with_viewer_token(self, client, viewer_headers):
        """Test viewer cannot access GET /audit-logs (403 Forbidden)."""
        response = client.get("/audit-logs", headers=viewer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_get_audit_logs_without_token(self, client):
        """Test GET /audit-logs fails without authentication."""
        response = client.get("/audit-logs")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Backup routes tests
    
    def test_get_backups_with_admin_token(self, client, admin_headers):
        """Test admin can access GET /backups."""
        response = client.get("/backups", headers=admin_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_backups_with_viewer_token(self, client, viewer_headers):
        """Test viewer can access GET /backups (read-only route)."""
        response = client.get("/backups", headers=viewer_headers)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
    
    def test_get_backups_without_token(self, client):
        """Test GET /backups fails without authentication."""
        response = client.get("/backups")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTokenExpiration:
    """Tests for token expiration and validation."""
    
    def test_expired_token_rejected(self, client):
        """Test that expired tokens are rejected."""
        # This test would require mocking time or using a very short expiration
        # For now, we test with an invalid token format which simulates expiration
        import jwt
        from app.settings import settings
        from datetime import datetime, timedelta
        
        # Create an expired token
        expired_payload = {
            "sub": "testadmin",
            "role": "admin",
            "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Token expired" in response.json()["detail"]
    
    def test_token_with_missing_subject(self, client):
        """Test that tokens without 'sub' claim are rejected."""
        import jwt
        from app.settings import settings
        from datetime import datetime, timedelta
        
        # Create a token without 'sub' claim
        invalid_payload = {
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        invalid_token = jwt.encode(invalid_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token payload" in response.json()["detail"]

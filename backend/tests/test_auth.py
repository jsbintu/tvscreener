"""
Bubby Vision — Auth Module Tests

Tests for JWT authentication: token creation, verification, model validation.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from app.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from app.auth.models import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    UpdateProfileRequest, ChangePasswordRequest,
)


# ──────────────────────────────────────────────
# JWT Handler Tests
# ──────────────────────────────────────────────


class TestJWTHandler:
    """Unit tests for JWT token creation and verification."""

    @patch("app.auth.jwt_handler.get_settings")
    def test_create_access_token(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_expiry_minutes = 15

        token = create_access_token(user_id="user-123")

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("app.auth.jwt_handler.get_settings")
    def test_create_refresh_token(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_refresh_expiry_days = 7

        token = create_refresh_token(user_id="user-123")

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("app.auth.jwt_handler.get_settings")
    def test_verify_valid_access_token(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_expiry_minutes = 15

        token = create_access_token(user_id="user-123")
        payload = verify_token(token, expected_type="access")

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    @patch("app.auth.jwt_handler.get_settings")
    def test_verify_valid_refresh_token(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_refresh_expiry_days = 7

        token = create_refresh_token(user_id="user-123")
        payload = verify_token(token, expected_type="refresh")

        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    @patch("app.auth.jwt_handler.get_settings")
    def test_verify_wrong_type_fails(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_expiry_minutes = 15

        token = create_access_token(user_id="user-123")
        payload = verify_token(token, expected_type="refresh")

        assert payload is None

    @patch("app.auth.jwt_handler.get_settings")
    def test_verify_invalid_token(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"

        payload = verify_token("invalid-token-string", expected_type="access")

        assert payload is None

    @patch("app.auth.jwt_handler.get_settings")
    def test_verify_wrong_secret(self, mock_settings):
        mock_settings.return_value.jwt_secret_key = "test-secret-key-for-jwt"
        mock_settings.return_value.jwt_algorithm = "HS256"
        mock_settings.return_value.jwt_access_expiry_minutes = 15

        token = create_access_token(user_id="user-123")

        # Change the secret for verification
        mock_settings.return_value.jwt_secret_key = "different-secret-key"
        payload = verify_token(token, expected_type="access")

        assert payload is None


# ──────────────────────────────────────────────
# Pydantic Model Tests
# ──────────────────────────────────────────────


class TestAuthModels:
    """Unit tests for auth Pydantic models."""

    def test_register_request_valid(self):
        req = RegisterRequest(
            email="user@example.com",
            password="MyS3cur3P@ss",
            display_name="Test User",
        )
        assert req.email == "user@example.com"
        assert req.password == "MyS3cur3P@ss"
        assert req.display_name == "Test User"

    def test_register_request_short_password(self):
        with pytest.raises(Exception):
            RegisterRequest(email="user@example.com", password="short")

    def test_login_request_valid(self):
        req = LoginRequest(email="user@example.com", password="password123")
        assert req.email == "user@example.com"

    def test_token_response(self):
        resp = TokenResponse(
            access_token="access.token.here",
            refresh_token="refresh.token.here",
            token_type="bearer",
            expires_in=900,
        )
        assert resp.access_token == "access.token.here"
        assert resp.token_type == "bearer"
        assert resp.expires_in == 900

    def test_user_response(self):
        resp = UserResponse(
            id="user-123",
            email="user@example.com",
            display_name="Test User",
            is_active=True,
            created_at="2024-01-01T00:00:00Z",
        )
        assert resp.id == "user-123"
        assert resp.is_active is True

    def test_update_profile_request_valid(self):
        req = UpdateProfileRequest(display_name="New Name")
        assert req.display_name == "New Name"

    def test_update_profile_request_none(self):
        req = UpdateProfileRequest()
        assert req.display_name is None

    def test_change_password_request_valid(self):
        req = ChangePasswordRequest(
            current_password="OldPassword1",
            new_password="NewSecure8+",
        )
        assert req.current_password == "OldPassword1"
        assert req.new_password == "NewSecure8+"

    def test_change_password_request_short(self):
        with pytest.raises(Exception):
            ChangePasswordRequest(
                current_password="OldPassword1",
                new_password="short",
            )

"""Tests for refresh-token rotation and revocation semantics."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_rejects_old(async_client: AsyncClient):
    """Old refresh token must be invalid immediately after successful rotation."""
    register_resp = await async_client.post(
        "/api/auth/register",
        json={
            "email": "refresh1@example.com",
            "username": "refresh_user_1",
            "password": "StrongPass123!",
            "full_name": "Refresh User",
        },
    )
    assert register_resp.status_code == 201
    first_refresh = register_resp.json()["refresh_token"]

    refresh_resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert refresh_resp.status_code == 200
    rotated_refresh = refresh_resp.json()["refresh_token"]
    assert rotated_refresh != first_refresh

    replay_resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert replay_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_fails_after_logout(async_client: AsyncClient):
    """Logging out should revoke current session, invalidating refresh token."""
    register_resp = await async_client.post(
        "/api/auth/register",
        json={
            "email": "refresh2@example.com",
            "username": "refresh_user_2",
            "password": "StrongPass123!",
            "full_name": "Refresh User 2",
        },
    )
    assert register_resp.status_code == 201
    data = register_resp.json()

    logout_resp = await async_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert logout_resp.status_code == 204

    refresh_resp = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh_resp.status_code == 401

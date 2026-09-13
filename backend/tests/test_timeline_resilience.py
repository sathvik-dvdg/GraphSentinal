# [WSL2]
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.services.timeline_service import (
    MAX_WINDOW_MINUTES,
    _get_epoch_expr,
    _parse_window_minutes,
    timeline_response,
)


def test_timeline_infinity_window_rejected(client, auth_headers):
    """DoS prevention: Ensure excessively large windows return 400 Bad Request."""
    resp = client.get("/api/v1/timeline", params={"last": "9999999999min"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "exceeds maximum limit" in resp.json()["detail"]


def test_timeline_oversized_string_rejected(client, auth_headers):
    """DoS prevention: Ensure string length overflow attempts return 400 Bad Request."""
    resp = client.get(
        "/api/v1/timeline",
        params={"last": "9" * 30 + "min"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"]


def test_timeline_malformed_format_rejected(client, auth_headers):
    """Ensure invalid syntax parameters return 400 Bad Request."""
    for invalid_val in ["invalid", "100seconds", "10x", "-15min", "abc"]:
        resp = client.get("/api/v1/timeline", params={"last": invalid_val}, headers=auth_headers)
        assert resp.status_code == 400, f"Expected 400 for {invalid_val}"
        assert "Invalid window parameter" in resp.json()["detail"] or "too long" in resp.json()["detail"]


def test_timeline_zero_window_rejected(client, auth_headers):
    """Ensure zero windows are rejected with 400 Bad Request."""
    resp = client.get("/api/v1/timeline", params={"last": "0min"}, headers=auth_headers)
    assert resp.status_code == 400
    assert "greater than zero" in resp.json()["detail"]


def test_timeline_valid_presets_and_custom(client, auth_headers):
    """Ensure all valid preset windows return 200 with structured data points."""
    for preset in ["60min", "24h", "7d", "14d", "30d", "all", "2h", "3d"]:
        resp = client.get("/api/v1/timeline", params={"last": preset}, headers=auth_headers)
        assert resp.status_code == 200, f"Failed for preset {preset}: {resp.text}"
        data = resp.json()
        assert "data_points" in data
        assert "bucket_minutes" in data
        assert isinstance(data["data_points"], list)
        assert len(data["data_points"]) <= 100


def test_parse_window_minutes_caps():
    """Unit test for window parser capping and limits."""
    minutes, bucket = _parse_window_minutes("30d")
    assert minutes == 30 * 24 * 60
    assert bucket == 24 * 60

    minutes, bucket = _parse_window_minutes("all")
    assert minutes == 30 * 24 * 60

    with pytest.raises(HTTPException) as exc_info:
        _parse_window_minutes("31d")
    assert exc_info.value.status_code == 400


def test_get_epoch_expr_dialect_swap():
    """Verify that _get_epoch_expr correctly handles postgresql and sqlite dialects."""
    mock_pg_session = MagicMock(spec=Session)
    mock_pg_bind = MagicMock()
    mock_pg_bind.dialect.name = "postgresql"
    mock_pg_session.get_bind.return_value = mock_pg_bind

    pg_expr = _get_epoch_expr(Incident.created_at, mock_pg_session)
    assert "extract" in str(pg_expr).lower()

    mock_sqlite_session = MagicMock(spec=Session)
    mock_sqlite_bind = MagicMock()
    mock_sqlite_bind.dialect.name = "sqlite"
    mock_sqlite_session.get_bind.return_value = mock_sqlite_bind

    sqlite_expr = _get_epoch_expr(Incident.created_at, mock_sqlite_session)
    assert "strftime" in str(sqlite_expr).lower()


def test_timeline_response_unit_of_work_requires_db():
    """Verify that timeline_response enforces dependency injection and Unit of Work."""
    from app.services.timeline_service import _timeline_cache
    _timeline_cache.clear()
    mock_session = MagicMock(spec=Session)
    mock_session.get_bind.return_value.dialect.name = "sqlite"
    mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

    res = timeline_response(db=mock_session, last="60min")
    assert "data_points" in res
    assert mock_session.query.called

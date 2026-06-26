"""Tests for MassIncidentClosure.

Run with:  pytest        (after `pip install pytest`)
The API layer is exercised against a fake requests.Session, so no network
access or real PagerDuty credentials are required.
"""
import json
from datetime import datetime, timezone

import pytest

import MassIncidentClosure as m


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.ok = status < 400
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise m.requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Records calls and replays queued responses."""

    def __init__(self, get_responses=None, put_responses=None):
        self._get_responses = list(get_responses or [])
        self._put_responses = list(put_responses or [])
        self.get_calls = []
        self.put_calls = []

    def get(self, url, params=None, **kw):
        # Copy params: paginate() mutates one dict across calls, so storing the
        # reference would let later mutations (e.g. offset) alter earlier records.
        self.get_calls.append((url, dict(params) if params else params))
        return self._get_responses.pop(0)

    def put(self, url, json=None, **kw):
        self.put_calls.append((url, json))
        return self._put_responses.pop(0)


# --------------------------------------------------------------------------- #
# parse_cutoff
# --------------------------------------------------------------------------- #
def test_parse_cutoff_defaults_to_midnight_utc():
    cutoff = m.parse_cutoff("2026-01-15")
    assert cutoff == datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)


def test_parse_cutoff_preserves_explicit_tz():
    cutoff = m.parse_cutoff("2026-01-15T12:00:00+02:00")
    assert cutoff.utcoffset().total_seconds() == 2 * 3600


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
def test_paginate_follows_more_flag():
    session = FakeSession(get_responses=[
        FakeResp(200, {"incidents": [{"id": "P1"}, {"id": "P2"}], "more": True}),
        FakeResp(200, {"incidents": [{"id": "P3"}], "more": False}),
    ])
    results = m.paginate(session, "/incidents", list_key="incidents")
    assert [r["id"] for r in results] == ["P1", "P2", "P3"]
    # offset advanced by PAGE_LIMIT on the second call
    assert session.get_calls[0][1]["offset"] == 0
    assert session.get_calls[1][1]["offset"] == m.PAGE_LIMIT


def test_paginate_stops_when_more_absent():
    session = FakeSession(get_responses=[
        FakeResp(200, {"services": [{"id": "S1"}]}),  # no 'more' key
    ])
    results = m.paginate(session, "/services", list_key="services")
    assert results == [{"id": "S1"}]
    assert len(session.get_calls) == 1


# --------------------------------------------------------------------------- #
# get_open_incidents — request shaping
# --------------------------------------------------------------------------- #
def test_get_open_incidents_single_request_with_filters():
    session = FakeSession(get_responses=[
        FakeResp(200, {"incidents": [{"id": "P1"}], "more": False}),
    ])
    until = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m.get_open_incidents(session, service_ids=["S1", "S2"], until=until)

    assert len(session.get_calls) == 1, "service filter must use a single request"
    params = session.get_calls[0][1]
    assert params["statuses[]"] == ["triggered", "acknowledged"]
    assert params["service_ids[]"] == ["S1", "S2"]
    assert params["until"] == until.isoformat()


def test_get_open_incidents_omits_optional_params():
    session = FakeSession(get_responses=[
        FakeResp(200, {"incidents": [], "more": False}),
    ])
    m.get_open_incidents(session)
    params = session.get_calls[0][1]
    assert "service_ids[]" not in params
    assert "until" not in params


# --------------------------------------------------------------------------- #
# close_incidents — bulk + chunking
# --------------------------------------------------------------------------- #
def test_close_incidents_bulk_single_put():
    incidents = [{"id": f"P{i}"} for i in range(3)]
    session = FakeSession(put_responses=[FakeResp(200, {})])
    closed = m.close_incidents(session, incidents)

    assert closed == 3
    assert len(session.put_calls) == 1
    sent = session.put_calls[0][1]["incidents"]
    assert [i["id"] for i in sent] == ["P0", "P1", "P2"]
    assert all(i["status"] == "resolved" for i in sent)


def test_close_incidents_chunks_large_batches():
    incidents = [{"id": str(i)} for i in range(m.BULK_CHUNK + 5)]
    session = FakeSession(put_responses=[FakeResp(200, {}), FakeResp(200, {})])
    closed = m.close_incidents(session, incidents)

    assert closed == m.BULK_CHUNK + 5
    assert len(session.put_calls) == 2
    assert len(session.put_calls[0][1]["incidents"]) == m.BULK_CHUNK
    assert len(session.put_calls[1][1]["incidents"]) == 5


def test_close_incidents_counts_only_successful_batches():
    incidents = [{"id": str(i)} for i in range(m.BULK_CHUNK + 1)]
    session = FakeSession(put_responses=[FakeResp(200, {}), FakeResp(400, {"error": "bad"})])
    closed = m.close_incidents(session, incidents)
    assert closed == m.BULK_CHUNK  # second (failed) batch not counted


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
def test_write_audit_log(tmp_path):
    path = tmp_path / "audit.log"
    incidents = [
        {"id": "P1", "service": {"summary": "API"}, "created_at": "2026-01-01T00:00:00Z"},
        {"id": "P2", "service": {"summary": "Web"}, "created_at": "2026-02-01T00:00:00Z"},
    ]
    m.write_audit_log(incidents, path=str(path))

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["id"] == "P1"
    assert rec["service"] == "API"
    assert "resolved_at" in rec


# --------------------------------------------------------------------------- #
# Session wiring
# --------------------------------------------------------------------------- #
def test_build_session_sets_headers_and_retries():
    session = m.build_session("tok", "me@example.com")
    assert session.headers["Authorization"] == "Token token=tok"
    assert session.headers["From"] == "me@example.com"
    adapter = session.get_adapter("https://api.pagerduty.com")
    assert adapter.max_retries.total == 5
    assert 429 in adapter.max_retries.status_forcelist


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

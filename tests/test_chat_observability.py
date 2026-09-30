from __future__ import annotations

import json
import asyncio
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.headers["x-response-time-ms"].replace(".", "", 1).isdigit()
    assert response.json()["correlation_id"] == correlation_id

    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_event = next(event for event in events if event["event"] == "request_received")
    response_event = next(event for event in events if event["event"] == "response_sent")
    for event in (request_event, response_event):
        assert event["correlation_id"] == correlation_id
        assert event["user_id_hash"]
        assert event["user_id_hash"] != "student-01"
        assert event["session_id"] == "session-01"
        assert event["feature"] == "qa"
        assert event["model"] == "claude-sonnet-4-5"
        assert event["env"] == "dev"
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_chat_uses_valid_request_id_and_scrubs_pii(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-a1b2c3d4"},
                json={
                    "user_id": "student-02",
                    "session_id": "session-02",
                    "feature": "qa",
                    "message": "Email student@example.com, phone 0901234567, "
                    "CCCD 001099012345, card 4111 1111 1111 1111",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-a1b2c3d4"
    log_text = log_path.read_text(encoding="utf-8")
    for raw_pii in (
        "student@example.com",
        "0901234567",
        "001099012345",
        "4111 1111 1111 1111",
    ):
        assert raw_pii not in log_text
    for marker in (
        "REDACTED_EMAIL",
        "REDACTED_PHONE_VN",
        "REDACTED_CCCD",
        "REDACTED_CREDIT_CARD",
    ):
        assert marker in log_text

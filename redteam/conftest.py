"""pytest fixtures for red team tests."""

import os
import pytest
from rtlib.client import RuneChatClient, DEFAULT_TARGET


def pytest_report_header(config):
    target = os.environ.get("RUNECHAT_TARGET", DEFAULT_TARGET)
    return f"runechat-redteam: target={target}"


@pytest.fixture
def client():
    """Unauthenticated client."""
    c = RuneChatClient()
    yield c
    c.cleanup()


@pytest.fixture
def authed_client():
    """Client logged in as a fresh user."""
    c = RuneChatClient()
    c.register()
    yield c
    c.cleanup()


@pytest.fixture
def victim_client():
    """Second authenticated client for cross-user tests."""
    c = RuneChatClient()
    c.register()
    yield c
    c.cleanup()


@pytest.fixture
def server_with_channel(authed_client):
    """Returns (server_id, channel_id) for the authed client's server."""
    sid = authed_client.create_server()
    cid = authed_client.create_channel(sid)
    return sid, cid

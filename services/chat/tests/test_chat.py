from unittest.mock import patch


def test_chat_returns_401_for_invalid_token(client, auth_headers):
    """Assert POST /api/chat returns 401 when api_client.get_me raises."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.side_effect = Exception("401 Unauthorized")
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 401


def test_chat_returns_403_for_non_premium(client, auth_headers):
    """Assert POST /api/chat returns 403 for non-premium, non-admin user."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.return_value = {
            "is_premium": False,
            "is_admin": False,
            "is_demo": False,
        }
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 403
    assert "Premium" in r.json()["detail"]


def test_chat_returns_403_for_demo_user(client, auth_headers):
    """Assert POST /api/chat returns 403 for demo account."""
    with patch("app.chat.routes.api_client") as mock_api:
        mock_api.get_me.return_value = {
            "is_premium": True,
            "is_admin": False,
            "is_demo": True,
        }
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
    assert r.status_code == 403


def test_chat_streams_for_premium_user(client, auth_headers):
    """Assert POST /api/chat returns 200 and streams SSE for premium user."""
    with patch("app.chat.routes.api_client") as mock_api, \
         patch("app.chat.routes.run_chat") as mock_run:
        mock_api.get_me.return_value = {
            "is_premium": True,
            "is_admin": False,
            "is_demo": False,
        }
        mock_run.return_value = iter(["Hello! ", "How can I help?"])
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_chat_streams_for_admin_user(client, auth_headers):
    """Assert POST /api/chat returns 200 for non-premium admin user."""
    with patch("app.chat.routes.api_client") as mock_api, \
         patch("app.chat.routes.run_chat") as mock_run:
        mock_api.get_me.return_value = {
            "is_premium": False,
            "is_admin": True,
            "is_demo": False,
        }
        mock_run.return_value = iter(["Sure thing!"])
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

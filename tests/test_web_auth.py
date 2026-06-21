"""Tests for the web device-code auth steps (simkl_api) and AuthManager."""
from unittest.mock import patch, MagicMock

import simkl_mps.simkl_api as simkl_api
from simkl_mps.web.auth import AuthManager


def _resp(status_code, json_data):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data
    return r


# --- simkl_api.request_pin ----------------------------------------------------

@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_request_pin_success(mock_get, _inet):
    mock_get.return_value = _resp(200, {
        "user_code": "ABCD1234",
        "verification_url": "https://simkl.com/pin",
        "expires_in": 900,
        "interval": 5,
    })
    pin = simkl_api.request_pin("cid")
    assert pin["user_code"] == "ABCD1234"
    assert pin["pin_url"] == "https://simkl.com/pin/ABCD1234"


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=False)
def test_request_pin_offline_returns_none(_inet):
    assert simkl_api.request_pin("cid") is None


# --- simkl_api.poll_pin_once --------------------------------------------------

@patch("simkl_mps.simkl_api.requests.get")
def test_poll_pin_once_authorized(mock_get):
    mock_get.return_value = _resp(200, {"result": "OK", "access_token": "tok123"})
    out = simkl_api.poll_pin_once("ABCD", "cid")
    assert out == {"status": "authorized", "access_token": "tok123"}


@patch("simkl_mps.simkl_api.requests.get")
def test_poll_pin_once_pending(mock_get):
    mock_get.return_value = _resp(200, {"result": "KO", "message": "Authorization pending"})
    assert simkl_api.poll_pin_once("ABCD", "cid")["status"] == "pending"


@patch("simkl_mps.simkl_api.requests.get")
def test_poll_pin_once_slow_down(mock_get):
    mock_get.return_value = _resp(200, {"result": "KO", "message": "Slow down"})
    assert simkl_api.poll_pin_once("ABCD", "cid")["status"] == "slow_down"


# --- AuthManager --------------------------------------------------------------

@patch("simkl_mps.web.auth.get_credentials")
def test_auth_manager_status_reflects_credentials(mock_creds):
    mock_creds.return_value = {"access_token": "tok", "user_id": 7}
    status = AuthManager().status()
    assert status["authenticated"] is True
    assert status["user_id"] == 7
    assert status["in_progress"] is False


@patch("simkl_mps.web.auth.get_credentials")
def test_auth_manager_start_missing_client_id(mock_creds):
    mock_creds.return_value = {"access_token": None}
    result = AuthManager().start()
    assert result == {"started": False, "reason": "missing_client_id"}


@patch("simkl_mps.simkl_api.finalize_authentication", return_value=99)
@patch("simkl_mps.simkl_api.poll_pin_once", return_value={"status": "authorized", "access_token": "tok"})
@patch("simkl_mps.simkl_api.request_pin")
@patch("simkl_mps.web.auth.get_credentials")
def test_auth_manager_full_flow_invokes_callback(mock_creds, mock_request, mock_poll, mock_final):
    mock_creds.return_value = {"client_id": "cid"}
    mock_request.return_value = {
        "user_code": "ABCD", "verification_url": "url", "pin_url": "purl",
        "expires_in": 900, "interval": 5,
    }
    captured = {}

    def on_auth(token, user_id):
        captured["token"] = token
        captured["user_id"] = user_id

    manager = AuthManager(on_authenticated=on_auth, poll_interval=0)
    result = manager.start()
    assert result["started"] is True
    assert result["user_code"] == "ABCD"

    manager._thread.join(timeout=2)
    assert captured == {"token": "tok", "user_id": 99}
    assert manager.status()["in_progress"] is False

"""Tests for Simkl API client_id_failed (412) handling."""
from unittest.mock import MagicMock, patch

import pytest

from simkl_mps.simkl_api import is_client_id_failed_response, pin_auth_flow


def _make_response(status_code, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("not json")
    return response


def test_is_client_id_failed_response_412_json():
    resp = _make_response(412, {"error": "client_id_failed"})
    assert is_client_id_failed_response(resp) is True


def test_is_client_id_failed_response_412_text():
    resp = _make_response(412, text='{"error":"client_id_failed"}')
    assert is_client_id_failed_response(resp) is True


def test_is_client_id_failed_response_other_status():
    resp = _make_response(500, {"error": "client_id_failed"})
    assert is_client_id_failed_response(resp) is False


@patch("simkl_mps.simkl_api.print_client_id_setup_instructions")
@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_pin_auth_flow_stops_on_client_id_failed(mock_get, _mock_inet, mock_print_instructions):
    mock_get.return_value = _make_response(412, {"error": "client_id_failed"})

    result = pin_auth_flow("bad-client-id")

    assert result is None
    assert mock_get.call_count == 1
    mock_print_instructions.assert_called_once()


@patch("simkl_mps.simkl_api.print_client_id_setup_instructions")
@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
@patch("simkl_mps.simkl_api.time.sleep")
def test_pin_auth_poll_no_retry_on_client_id_failed(
    mock_sleep, mock_get, _mock_inet, mock_print_instructions
):
    pin_init = _make_response(
        200,
        {
            "user_code": "ABCD1234",
            "verification_url": "https://simkl.com/oauth/authorize",
            "expires_in": 60,
            "interval": 5,
        },
    )
    poll_failed = _make_response(412, {"error": "client_id_failed"})
    mock_get.side_effect = [pin_init, poll_failed]

    result = pin_auth_flow("bad-client-id")

    assert result is None
    assert mock_get.call_count == 2
    mock_sleep.assert_not_called()
    mock_print_instructions.assert_called_once()

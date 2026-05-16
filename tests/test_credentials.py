"""Tests for credential resolution."""
from pathlib import Path
from unittest.mock import patch

import pytest

from simkl_mps import credentials


def test_is_usable_credential():
    assert credentials._is_usable_credential(None) is False
    assert credentials._is_usable_credential("") is False
    assert credentials._is_usable_credential("SIMKL_CLIENT_ID_PLACEHOLDER") is False
    assert credentials._is_usable_credential("real-client-id") is True


def test_get_credentials_reads_dev_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SIMKL_CLIENT_ID=env-client-id\n"
        "SIMKL_CLIENT_SECRET=env-client-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(credentials, "SIMKL_CLIENT_ID", "")
    monkeypatch.setattr(credentials, "SIMKL_CLIENT_SECRET", "")
    monkeypatch.setattr(credentials, "DEV_CREDS_PATH", env_file)
    monkeypatch.setattr(
        credentials,
        "ENV_FILE_PATH",
        tmp_path / "missing.simkl_mps.env",
    )

    with patch.object(credentials, "get_env_file_path", return_value=tmp_path / "missing.simkl_mps.env"):
        creds = credentials.get_credentials()

    assert creds["client_id"] == "env-client-id"
    assert creds["client_secret"] == "env-client-secret"


def test_get_credentials_ignores_placeholder_module_vars(monkeypatch):
    monkeypatch.setattr(credentials, "SIMKL_CLIENT_ID", credentials.CLIENT_ID_PLACEHOLDER)
    monkeypatch.setattr(credentials, "SIMKL_CLIENT_SECRET", credentials.CLIENT_SECRET_PLACEHOLDER)
    monkeypatch.setattr(credentials, "DEV_CREDS_PATH", Path("/nonexistent/.env"))

    with patch.object(credentials, "get_env_file_path", return_value=Path("/nonexistent/.simkl_mps.env")):
        with patch.dict("os.environ", {}, clear=True):
            creds = credentials.get_credentials()

    assert creds["client_id"] is None
    assert creds["client_secret"] is None

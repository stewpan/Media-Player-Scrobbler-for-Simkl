"""Tests for the data-directory migration to ~/.simkl-mps.

All tests redirect Path.home() to a tmp dir, so the real user data is untouched.
"""
import pathlib

import pytest

import simkl_mps.migration as migration


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    return tmp_path


def _seed(dir_path, name="settings.json", content="{}"):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / name).write_text(content)


def test_migrates_kavin_to_dot_simkl_mps(fake_home):
    legacy = fake_home / "kavin" / "simkl-mps"
    _seed(legacy, "settings.json", '{"v": 1}')

    assert migration.migrate_user_directory() is True

    new = fake_home / ".simkl-mps"
    assert (new / "settings.json").read_text() == '{"v": 1}'
    assert not legacy.exists()
    assert not (fake_home / "kavin").exists()  # empty legacy parent removed


def test_migrates_oldest_legacy_dir(fake_home):
    legacy = fake_home / "kavinthangavel" / "simkl-mps"
    _seed(legacy, "creds", "token")

    migration.migrate_user_directory()

    assert (fake_home / ".simkl-mps" / "creds").read_text() == "token"


def test_no_migration_when_new_dir_exists(fake_home):
    # Existing data in the new location must never be overwritten by a legacy dir.
    new = fake_home / ".simkl-mps"
    _seed(new, "settings.json", '{"keep": true}')
    legacy = fake_home / "kavin" / "simkl-mps"
    _seed(legacy, "settings.json", '{"stale": true}')

    migration.migrate_user_directory()

    assert (new / "settings.json").read_text() == '{"keep": true}'
    assert legacy.exists()  # left untouched


def test_no_legacy_is_a_noop(fake_home):
    assert migration.migrate_user_directory() is True
    assert not (fake_home / ".simkl-mps").exists()  # nothing created by a no-op move


def test_get_app_data_dir_creates_canonical_dir(fake_home):
    path = migration.get_app_data_dir()
    assert path == fake_home / ".simkl-mps"
    assert path.is_dir()

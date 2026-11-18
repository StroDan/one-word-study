"""Shared test setup."""
import pytest

import app


@pytest.fixture(autouse=True)
def never_touch_the_real_save_file(tmp_path, monkeypatch):
    """R10: a test that forgets to pass save_path still writes to a temporary folder,
    never to ~/.one-word-study."""
    monkeypatch.setattr(app, "DEFAULT_SAVE_PATH", tmp_path / "default" / "cards.json")

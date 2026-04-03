"""Tests for src.json_storage — LocalJSONStorage save/load roundtrip."""

from pathlib import Path

import pytest

from src.json_storage import LocalJSONStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalJSONStorage:
    return LocalJSONStorage(filepath=tmp_path / ".state.json")


class TestLocalJSONStorage:
    def test_save_and_load(self, storage: LocalJSONStorage):
        data = {"name": "test", "values": [1, 2, 3]}
        path = storage.save(data)
        assert Path(path).exists()

        loaded = storage.load()
        assert loaded == data

    def test_save_overwrites(self, storage: LocalJSONStorage):
        storage.save({"version": 1})
        storage.save({"version": 2})

        loaded = storage.load()
        assert loaded["version"] == 2

    def test_load_no_file_raises(self, storage: LocalJSONStorage):
        with pytest.raises(FileNotFoundError):
            storage.load()

    def test_save_creates_parent_directory(self, tmp_path: Path):
        nested = tmp_path / "sub" / "dir" / ".state.json"
        s = LocalJSONStorage(filepath=nested)
        s.save({"ok": True})
        assert nested.exists()

    def test_roundtrip_nested_data(self, storage: LocalJSONStorage):
        data = {
            "protocols": [
                {"name": "P1", "duration": 600},
                {"name": "P2", "duration": 30},
            ],
            "metadata": {"created": "2025-01-01T00:00:00"},
        }
        storage.save(data)
        loaded = storage.load()
        assert loaded == data

    def test_unicode_data(self, storage: LocalJSONStorage):
        data = {"name": "テスト", "description": "日本語テスト"}
        storage.save(data)
        loaded = storage.load()
        assert loaded == data

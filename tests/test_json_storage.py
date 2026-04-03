"""Tests for src.json_storage — LocalJSONStorage save/load roundtrip."""

from pathlib import Path

import pytest

from src.json_storage import LocalJSONStorage


@pytest.fixture
def storage(tmp_path: Path) -> LocalJSONStorage:
    return LocalJSONStorage(base_dir=tmp_path)


class TestLocalJSONStorage:
    def test_save_and_load_with_key(self, storage: LocalJSONStorage):
        data = {"name": "test", "values": [1, 2, 3]}
        path = storage.save(data, key="mykey")
        assert Path(path).exists()

        loaded = storage.load(key="mykey")
        assert loaded == data

    def test_save_auto_key(self, storage: LocalJSONStorage):
        data = {"hello": "world"}
        path = storage.save(data)
        assert Path(path).exists()

        loaded = storage.load()  # loads most recent
        assert loaded == data

    def test_load_most_recent(self, storage: LocalJSONStorage):
        storage.save({"version": 1}, key="aaa")
        storage.save({"version": 2}, key="bbb")

        # load without key returns most recently modified
        loaded = storage.load()
        assert loaded["version"] == 2

    def test_load_no_files_raises(self, storage: LocalJSONStorage):
        with pytest.raises(FileNotFoundError):
            storage.load()

    def test_save_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "sub" / "dir"
        s = LocalJSONStorage(base_dir=nested)
        s.save({"ok": True}, key="test")
        assert (nested / "test.json").exists()

    def test_roundtrip_nested_data(self, storage: LocalJSONStorage):
        data = {
            "protocols": [
                {"name": "P1", "duration": 600},
                {"name": "P2", "duration": 30},
            ],
            "metadata": {"created": "2025-01-01T00:00:00"},
        }
        storage.save(data, key="complex")
        loaded = storage.load(key="complex")
        assert loaded == data

    def test_unicode_data(self, storage: LocalJSONStorage):
        data = {"name": "テスト", "description": "日本語テスト"}
        storage.save(data, key="unicode")
        loaded = storage.load(key="unicode")
        assert loaded == data

    def test_overwrite_existing_key(self, storage: LocalJSONStorage):
        storage.save({"v": 1}, key="same")
        storage.save({"v": 2}, key="same")
        loaded = storage.load(key="same")
        assert loaded["v"] == 2

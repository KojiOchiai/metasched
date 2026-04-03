import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class JSONStorage(ABC):
    """Abstract base class for storing and retrieving JSON data."""

    @abstractmethod
    def save(self, data: Any) -> str:
        """Save JSON data. Returns the path or reference to the saved data."""
        pass

    @abstractmethod
    def load(self) -> Any:
        """Load JSON data."""
        pass


class LocalJSONStorage(JSONStorage):
    """
    Persists state to a single JSON file, overwritten on every save.
    """

    def __init__(self, filepath: str | Path = ".state.json"):
        self.filepath = Path(filepath)

    def save(self, data: Any) -> str:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(self.filepath)

    def load(self) -> Any:
        if not self.filepath.exists():
            raise FileNotFoundError(f"State file not found: {self.filepath}")
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class JSONStorage(ABC):
    """
    Abstract base class for storing and retrieving JSON data.
    Implement concrete subclasses for each storage backend
    (e.g. local file system, S3, database).
    """

    @abstractmethod
    def save(self, data: Any, key: Optional[str] = None) -> str:
        """
        Save JSON data.

        Args:
            data: A Python object (JSON serializable).
            key: Optional unique key or identifier for the storage location.

        Returns:
            str: The key or path reference to the saved data.
        """
        pass

    @abstractmethod
    def load(self, key: str) -> Any:
        """
        Load JSON data.

        Args:
            key: The key or path returned by the save() method.

        Returns:
            Any: The loaded Python object.
        """
        pass
        pass


class LocalJSONStorage(JSONStorage):
    """
    A concrete implementation of JSONStorage
    that stores JSON files on the local file system.
    """

    def __init__(self, base_dir: str = "payloads"):
        # Directory where JSON files will be stored
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: Any, key: Optional[str] = None) -> str:
        # Generate a unique key if not provided
        if key is None:
            key = str(uuid.uuid4())
            key = datetime.now().strftime("%Y%m%d_%H%M%S_%f_") + str(key)

        # Build the file path
        filepath = self.base_dir / f"{key}.json"

        # Write JSON to file with UTF-8 encoding
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Return the file path as a string
        return str(filepath)

    def load(self, key: str) -> Any:
        # Allow passing either a full path or just the key
        filepath = Path(key)
        if not filepath.exists():
            filepath = self.base_dir / f"{key}.json"

        # Read JSON from file
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

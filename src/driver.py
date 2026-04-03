import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("driver")
logger.setLevel(logging.INFO)


class Driver(ABC):
    @abstractmethod
    async def run(self, protocol: str) -> list[str] | None:
        raise NotImplementedError

    @abstractmethod
    async def move(self, what: str, from_: str, to: str):
        raise NotImplementedError


class DummyDriver(Driver):
    async def run(self, protocol: str) -> list[str] | None:
        logger.info(
            {"function": "DummyDriver.run", "type": "start", "protocol": protocol}
        )
        await asyncio.sleep(2)
        logger.info(
            {"function": "DummyDriver.run", "type": "end", "protocol": protocol}
        )
        return None

    async def move(self, what: str, from_: str, to: str):
        pass


def create_driver(name: str) -> Driver:
    if name == "maholo":
        from drivers.maholo.driver import MaholoDriver
        from src.settings import maholo_settings

        return MaholoDriver(
            host=maholo_settings.host,
            port=maholo_settings.port,
            base_path=maholo_settings.base_path,
            microscope_image_dir=maholo_settings.microscope_image_dir,
        )
    return DummyDriver()
